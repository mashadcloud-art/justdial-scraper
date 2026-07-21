"""
Aster Hospitals (asterhospitals.in) scraper — server-rendered Drupal 11 site, no
auth/token needed. Pure fetch+parse functions; DB writes and pacing live in service.py.

Selectors below were confirmed against the live site (2026-07):
  - Hospital detail page (/hospitals/{slug}): name from the breadcrumb JSON-LD (the
    generic "Organization" JSON-LD block is a shared/cached template with wrong data
    on some pages — don't use it), about from .field--name-field-excerpt +
    .ckeditor-readmore, address from .field--name-field-address, email is Cloudflare-
    obfuscated (data-cfemail, decoded with the standard XOR scheme), specialities from
    the view--display-id-specialities_listing block, coordinates from the Google Maps
    embed iframe's pb= parameter.
  - Doctor listing page (/doctors/hospital/{slug}-{id}): Drupal Views with a plain
    ?page=N pager (0-indexed, no AJAX/POST needed) inside
    view--id-aster_search / view--display-id-doctor_search, 5 cards per page, ends
    when a page returns zero .views-row cards.
"""
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.asterhospitals.in"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9"}
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3
MAX_DOCTOR_PAGES = 60  # safety cap (~300 doctors) so a pager bug can't loop forever


def _get(url: str) -> Optional[requests.Response]:
    """GET with retry + exponential backoff. Returns None (not raises) on final failure
    or a genuine 404, so callers can record the failure and move on."""
    delay = 2
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(delay)
            delay *= 2
    return None


def _text(el) -> Optional[str]:
    return el.get_text(" ", strip=True) if el else None


def _decode_cfemail(encoded: str) -> Optional[str]:
    try:
        r = int(encoded[:2], 16)
        return "".join(chr(int(encoded[i:i + 2], 16) ^ r) for i in range(2, len(encoded), 2))
    except Exception:
        return None


# ─── Part 1: hospital detail page ─────────────────────────────────────────────

def resolve_detail_slug(doctors_slug: str) -> Optional[str]:
    """The /hospitals/{slug} detail-page slug sometimes differs from the doctors-
    listing slug (e.g. doctors-listing 'aster-mother-areekode' vs detail-page
    'aster-mims-mother-areekode'). Try the direct slug first (works for 15/18);
    fall back to fuzzy-matching against the /hospitals index for the rest, rather
    than hardcoding a mapping that would silently go stale if the site changes."""
    resp = _get(f"{BASE_URL}/hospitals/{doctors_slug}")
    if resp is not None:
        # Drupal redirects near-miss slugs to the canonical one — use the resolved
        # URL's slug, not the guess, so a later direct fetch doesn't rely on a slug
        # that only happened to work via redirect.
        m = re.search(r"/hospitals/([a-z0-9-]+)/?$", resp.url)
        return m.group(1) if m else doctors_slug

    resp = _get(f"{BASE_URL}/hospitals")
    if resp is None:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    candidates = set()
    for a in soup.find_all("a", href=True):
        m = re.match(r"^(?:https://www\.asterhospitals\.in)?/hospitals/([a-z0-9-]+)$", a["href"])
        if m:
            candidates.add(m.group(1))

    target_tokens = set(doctors_slug.split("-"))
    best_slug, best_overlap = None, 0
    for cand in candidates:
        overlap = len(target_tokens & set(cand.split("-")))
        if overlap > best_overlap:
            best_slug, best_overlap = cand, overlap
    return best_slug if best_overlap >= 2 else None


def scrape_hospital(doctors_slug: str, aster_id: int) -> dict:
    """Returns a dict matching AsterHospital columns, plus 'ok'/'error' keys."""
    detail_slug = resolve_detail_slug(doctors_slug)
    if not detail_slug:
        return {"ok": False, "error": f"Could not resolve a /hospitals detail page for '{doctors_slug}'", "slug": doctors_slug}

    url = f"{BASE_URL}/hospitals/{detail_slug}"
    resp = _get(url)
    if resp is None:
        return {"ok": False, "error": f"Failed to fetch {url}", "slug": doctors_slug, "detail_slug": detail_slug}

    soup = BeautifulSoup(resp.text, "html.parser")
    data = {"ok": True, "slug": doctors_slug, "detail_slug": detail_slug, "source_url": url}

    # Name: last breadcrumb item is reliable per-page; the generic Organization
    # JSON-LD block is a shared cached template and can carry another hospital's data.
    name = None
    for script in soup.find_all("script", type="application/ld+json"):
        if script.string and '"BreadcrumbList"' in script.string:
            items = re.findall(r'"name"\s*:\s*"([^"]+)"', script.string)
            if items:
                name = items[-1]
            break
    if not name and soup.title:
        name = soup.title.get_text(strip=True).split(" - ")[0].strip()
    data["name"] = name

    excerpt = soup.find(class_="field--name-field-excerpt")
    readmore = soup.find(class_="ckeditor-readmore")
    about_parts = [t for t in (_text(excerpt), _text(readmore)) if t]
    data["about"] = "\n\n".join(about_parts) or None

    addr_field = soup.find(class_="field--name-field-address")
    address = _text(addr_field)
    if address:
        address = re.sub(r"^Address\s*", "", address).strip()
    data["address"] = address or None

    contact = soup.find(class_="field--name-field-contact-info")
    contact_text = _text(contact) or ""
    emergency_m = re.search(r"Emergency\s*([\d\s+\-]{7,})", contact_text)
    helpline_m = re.findall(r"\+\s?\d[\d\s\-]{7,}\d", contact_text.split("Helpline", 1)[-1]) if "Helpline" in contact_text else []
    data["phone"] = emergency_m.group(1).strip() if emergency_m else None
    data["helpline"] = ", ".join(h.strip() for h in helpline_m) or None

    cf = soup.find(class_="__cf_email__")
    data["email"] = _decode_cfemail(cf.get("data-cfemail")) if cf else None

    spec_block = soup.find("div", class_=re.compile(r"view--display-id-specialities_listing"))
    if spec_block:
        specialities = [a.get_text(strip=True) for a in spec_block.find_all("a") if a.get_text(strip=True)]
        data["specialities"] = ", ".join(dict.fromkeys(specialities)) or None  # dict.fromkeys = dedupe, keep order
    else:
        data["specialities"] = None

    # No dedicated "facilities" section exists site-wide; best-effort search for one.
    facilities_heading = next(
        (h for h in soup.find_all(re.compile(r"^h[2-3]$"))
         if re.search(r"facilit|amenit|infrastructure", h.get_text(strip=True), re.IGNORECASE)),
        None,
    )
    if facilities_heading:
        container = facilities_heading.find_parent(["section", "div"])
        items = [a.get_text(strip=True) for a in container.find_all("a")] if container else []
        data["facilities"] = ", ".join(dict.fromkeys(i for i in items if i)) or None
    else:
        data["facilities"] = None

    iframe = soup.find("iframe", src=re.compile(r"google\.com/maps/embed"))
    if iframe:
        m = re.search(r"!2d([\-\d.]+)!3d([\-\d.]+)", iframe["src"])
        if m:
            data["longitude"], data["latitude"] = float(m.group(1)), float(m.group(2))
    map_link = soup.find("a", href=re.compile(r"goo\.gl/maps|maps\.app\.goo\.gl|maps\.google\.com"))
    data["map_link"] = map_link["href"] if map_link else None

    return data


# ─── Part 2: doctor listing (paginated) ───────────────────────────────────────

def _parse_doctor_cards(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    view = soup.find("div", class_="view--id-aster_search")
    if view is None:
        return []
    doctors = []
    for row in view.find_all(class_="views-row"):
        name_a = row.select_one(".doctor-name a")
        if not name_a:
            continue
        href = name_a.get("href") or ""
        doctors.append({
            "name": name_a.get_text(strip=True),
            "detail_url": BASE_URL + href if href.startswith("/") else href,
            "designation": _text(row.select_one(".doctor-designation")),
            "qualifications": _text(row.select_one(".doctor-qualification")),
            "speciality": re.sub(r"^SPECIALITY\s*", "", _text(row.select_one(".speciality")) or "").strip() or None,
            "hospital_name_raw": re.sub(r"^HOSPITAL\s*", "", _text(row.select_one(".hospital")) or "").strip() or None,
            "bio_snippet": _text(row.select_one(".doctor-bio")),
        })
    return doctors


def scrape_doctors(doctors_url_slug_id: str, on_page=None) -> dict:
    """doctors_url_slug_id is e.g. 'aster-mims-kannur-1300'. Pages through ?page=N
    (0-indexed) until a page returns zero cards. `on_page(page_num, doctors)` is an
    optional callback so the caller can persist incrementally instead of buffering
    the whole hospital in memory."""
    base = f"{BASE_URL}/doctors/hospital/{doctors_url_slug_id}"
    all_doctors = []
    for page in range(MAX_DOCTOR_PAGES):
        url = base if page == 0 else f"{base}?page={page}"
        resp = _get(url)
        if resp is None:
            if page == 0:
                return {"ok": False, "error": f"Failed to fetch {url}", "doctors": []}
            break
        doctors = _parse_doctor_cards(resp.text)
        if not doctors:
            break
        all_doctors.extend(doctors)
        if on_page:
            on_page(page, doctors)
        if page < MAX_DOCTOR_PAGES - 1:
            time.sleep(1.5)
    return {"ok": True, "doctors": all_doctors}
