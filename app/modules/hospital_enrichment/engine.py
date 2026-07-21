"""
Hospital enrichment crawler engine.

Pure functions over a single (listing, profile) pair — no DB session handling here
beyond what the caller passes in for writing gallery/doctor rows. Kept separate from
service.py (job orchestration / threading) so the crawling heuristics can be tested
and tuned on their own, the same way app/scraper/deep_category_scraper.py is split
out from app/modules/deep_scrape/service.py.

Website discovery, gallery extraction and doctor-page extraction are all heuristic —
hospital websites vary wildly in markup, so this aims for "works on most WordPress/
Wix/Squarespace-ish small business sites" rather than 100% coverage. Every failure
mode is recorded on the profile (website_status / gallery_status / doctors_page_status
+ error_detail) rather than raising, and HospitalDoctor.raw_text keeps the unparsed
card text so uncertain extractions can be reviewed/improved later instead of silently
dropped.
"""
import re
import difflib
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9"}
REQUEST_TIMEOUT = 15
MAX_GALLERY_IMAGES = 40
MAX_DOCTORS = 60
WEBSITE_MATCH_THRESHOLD = 0.42

# Domains that are never a hospital's "official website" even if they show up in
# jd_url or search results — directories, socials, maps, aggregators.
EXCLUDED_DOMAINS = [
    "justdial.com", "jd.in",
    "google.com", "goo.gl", "maps.app.goo.gl", "g.page",
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "youtu.be", "pinterest.com",
    "practo.com", "lybrate.com", "sulekha.com", "indiamart.com",
    "yellowpages.in", "tradeindia.com", "whatsapp.com", "wa.me",
    "wikipedia.org", "duckduckgo.com", "bing.com", "yahoo.com",
]

GALLERY_LINK_KEYWORDS = [
    "gallery", "photo gallery", "photos", "image gallery", "photo-gallery",
    "our gallery", "media", "hospital-gallery",
]
GALLERY_PATH_GUESSES = ["/gallery", "/photo-gallery", "/photos", "/image-gallery", "/media/gallery"]

DOCTOR_LINK_KEYWORDS = [
    "our doctors", "doctors", "our team", "our-team", "meet the team", "meet our team",
    "physicians", "specialists", "consultants", "medical team", "medical-team",
    "find a doctor", "doctor list", "our specialists", "team", "faculty", "experts",
]
DOCTOR_PATH_GUESSES = [
    "/our-team", "/our-doctors", "/doctors", "/team", "/medical-team",
    "/find-a-doctor", "/specialists", "/our-specialists", "/consultants",
]

QUALIFICATION_TOKENS = [
    "MBBS", "MD", "MS", "MDS", "BDS", "BAMS", "BHMS", "BUMS", "DNB", "DM", "MCh",
    "FRCS", "MRCP", "MRCS", "DGO", "DCH", "DA", "DLO", "DVD", "PhD", "FICS",
    "FICOG", "DDVL", "DPM", "FACS", "MRCOG", "FRCOG", "DipNB", "PGDCC", "FCPS",
    "MCPS", "FAGE", "FISCP", "MNAMS",
]
QUALIFICATION_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in QUALIFICATION_TOKENS) + r")\b", re.IGNORECASE
)
EXPERIENCE_RE = re.compile(r"(\d{1,2}\s?\+?\s?(?:years|yrs|yr)\b)", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}\b")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_SKIP_IMAGE_HINTS = ("logo", "favicon", "icon-", "sprite", "placeholder", "avatar-default", "blank.")


def now():
    return datetime.utcnow()


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _get(url: str) -> Optional[requests.Response]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if resp.status_code >= 400:
            return None
        return resp
    except requests.RequestException:
        return None


def _soup(resp: requests.Response) -> BeautifulSoup:
    return BeautifulSoup(resp.text, "html.parser")


def domain_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def _is_excluded_domain(domain: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in EXCLUDED_DOMAINS)


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


# ─── Step 1: website resolution ───────────────────────────────────────────────

def existing_website_candidate(listing) -> Optional[str]:
    """A listing's jd_url only counts as its official website when it points at a
    real external domain — for JustDial-sourced rows jd_url is the JD listing page
    itself, not the hospital's site, so those are correctly excluded here."""
    url = normalize_url(getattr(listing, "jd_url", None) or "")
    if not url:
        return None
    domain = domain_of(url)
    if not domain or _is_excluded_domain(domain):
        return None
    return url


def _clean_text(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def _similarity(a: str, b: str) -> float:
    a, b = _clean_text(a), _clean_text(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def search_candidates(page, name: str, city: str) -> list:
    """DuckDuckGo search via a real (headless) browser tab. Returns [(url, title), ...].

    DuckDuckGo's static /html/ endpoint (and Bing's plain HTML results) reliably serve
    an anti-bot challenge to plain requests.get() — even with full browser headers —
    because they fingerprint the TLS/JS client, not just headers. The JS-rendered
    duckduckgo.com site behind a real Chromium tab does not trigger that wall, so the
    search step needs an actual Playwright page; `page` is owned and reused across an
    entire job run by service.py rather than launched per listing, to keep it cheap.
    """
    if page is None:
        return []
    query = f"{name} {city} official website".strip()
    try:
        page.goto(f"https://duckduckgo.com/?q={requests.utils.quote(query)}", timeout=20000)
        page.wait_for_selector('a[data-testid="result-title-a"]', timeout=6000)
    except Exception:
        return []

    try:
        raw = page.eval_on_selector_all(
            'a[data-testid="result-title-a"]',
            "els => els.map(e => ({href: e.href, text: e.innerText}))",
        )
    except Exception:
        return []

    results = []
    for item in raw:
        href, title = item.get("href") or "", item.get("text") or ""
        domain = domain_of(href)
        if not domain or _is_excluded_domain(domain):
            continue
        results.append((href, title))
        if len(results) >= 8:
            break
    return results


# Words too generic to count as evidence of a name match on their own — "City Hospital"
# vs "District Hospital" share "hospital" but are different businesses. Character-level
# SequenceMatcher alone over-scores exactly this case (lots of shared common words), so
# matching requires actual overlap on the *distinctive* (non-generic) part of the name.
GENERIC_NAME_WORDS = {
    "hospital", "hospitals", "clinic", "clinics", "medical", "medicals", "center", "centre",
    "nursing", "home", "homes", "care", "health", "healthcare", "multispecialty", "multi",
    "speciality", "specialty", "the", "and", "of", "in", "for", "pvt", "ltd", "private",
    "limited", "institute", "foundation", "trust", "society", "general", "district",
}


def _distinctive_tokens(name: str) -> list:
    return [t for t in _clean_text(name).split() if t not in GENERIC_NAME_WORDS and len(t) > 2]


def pick_best_website(candidates: list, name: str, city: str):
    """Returns (url, score) for the best name+city match, or (None, 0.0).

    Requires actual overlap on the hospital's distinctive name tokens (its proper-noun
    part) rather than trusting raw character similarity, which scores generic names like
    "City Hospital" as a strong match against any unrelated hospital in the same city.
    """
    distinctive = _distinctive_tokens(name)
    best_url, best_score = None, 0.0
    for url, title in candidates:
        domain = domain_of(url)
        domain_words = set(re.split(r"[.\-]", domain))
        title_words = set(_clean_text(title).split())

        if distinctive:
            hits = sum(1 for t in distinctive if t in title_words or any(t in dw for dw in domain_words))
            token_score = hits / len(distinctive)
            if hits == 0:
                continue  # no distinctive-name evidence at all — don't let city/generic words carry a match
        else:
            # Fully generic name (e.g. "City Hospital") — nothing distinctive to verify
            # against, so demand a much stronger overall similarity before trusting it.
            token_score = 0.0

        char_score = max(_similarity(name, title), _similarity(name, domain.replace("-", " ").replace(".", " ")))
        score = (0.7 * token_score) + (0.3 * char_score) if distinctive else char_score * 0.6

        haystack = f"{title} {url}".lower()
        if city and city.lower().strip() and city.lower().strip() in haystack:
            score = min(1.0, score + 0.1)
        if score > best_score:
            best_url, best_score = url, score
    if best_score >= WEBSITE_MATCH_THRESHOLD:
        return best_url, round(best_score, 3)
    return None, 0.0


# ─── Step 2: gallery ───────────────────────────────────────────────────────────

def _internal_links(soup: BeautifulSoup, base_url: str) -> list:
    base_domain = domain_of(base_url)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if domain_of(absolute) != base_domain:
            continue
        links.append((a.get_text(strip=True), absolute))
    return links


def _find_page_by_keywords(base_url: str, home_soup: BeautifulSoup, keywords: list, path_guesses: list) -> Optional[str]:
    for text, href in _internal_links(home_soup, base_url):
        haystack = f"{text} {href}".lower()
        if any(kw in haystack for kw in keywords):
            return href
    for path in path_guesses:
        candidate = urljoin(base_url, path)
        resp = _get(candidate)
        if resp is not None:
            return resp.url
    return None


def find_gallery_page(base_url: str, home_soup: BeautifulSoup) -> Optional[str]:
    return _find_page_by_keywords(base_url, home_soup, GALLERY_LINK_KEYWORDS, GALLERY_PATH_GUESSES)


def _resolve_image_src(img, base_url: str) -> Optional[str]:
    for attr in ("src", "data-src", "data-lazy-src", "data-original"):
        val = img.get(attr)
        if val and not val.startswith("data:"):
            return urljoin(base_url, val.strip())
    srcset = img.get("srcset") or img.get("data-srcset")
    if srcset:
        first = srcset.split(",")[0].strip().split(" ")[0]
        if first and not first.startswith("data:"):
            return urljoin(base_url, first)
    return None


def _extract_images_from_soup(soup: BeautifulSoup, page_url: str) -> list:
    urls = []
    seen = set()
    for img in soup.find_all("img"):
        src = _resolve_image_src(img, page_url)
        if not src:
            continue
        lower = src.lower()
        if any(hint in lower for hint in _SKIP_IMAGE_HINTS):
            continue
        if lower.endswith(".svg"):
            continue
        # Skip obviously tiny icons when dimensions are declared in markup
        try:
            w, h = int(img.get("width", 0) or 0), int(img.get("height", 0) or 0)
            if 0 < w < 60 and 0 < h < 60:
                continue
        except ValueError:
            pass
        if src not in seen:
            seen.add(src)
            urls.append(src)
        if len(urls) >= MAX_GALLERY_IMAGES:
            break
    return urls


def extract_gallery_images(gallery_url: Optional[str], home_soup: BeautifulSoup, home_url: str) -> list:
    """Extract from a dedicated gallery page if we found one; otherwise fall back to
    any slider/carousel/gallery section embedded directly in the homepage."""
    if gallery_url:
        resp = _get(gallery_url)
        if resp is not None:
            return _extract_images_from_soup(_soup(resp), gallery_url)

    sections = home_soup.find_all(
        class_=re.compile(r"(gallery|slider|carousel|swiper|lightbox)", re.IGNORECASE)
    )
    urls, seen = [], set()
    for section in sections:
        for src in _extract_images_from_soup(section, home_url):
            if src not in seen:
                seen.add(src)
                urls.append(src)
    return urls[:MAX_GALLERY_IMAGES]


# ─── Step 3: doctors / team page ──────────────────────────────────────────────

def find_doctors_page(base_url: str, home_soup: BeautifulSoup) -> Optional[str]:
    return _find_page_by_keywords(base_url, home_soup, DOCTOR_LINK_KEYWORDS, DOCTOR_PATH_GUESSES)


def _looks_like_doctor_card(tag) -> bool:
    if tag.find("img") is None:
        return False
    if tag.find(re.compile(r"^h[1-6]$")) is None and tag.find(["strong", "b"]) is None:
        return False
    return True


def _find_doctor_cards(soup: BeautifulSoup) -> list:
    candidates = soup.find_all(
        class_=re.compile(r"(doctor|physician|team[-_ ]?member|staff[-_ ]?member|consultant|specialist)", re.IGNORECASE)
    )
    cards = [c for c in candidates if _looks_like_doctor_card(c)]
    if cards:
        # Prefer the smallest matching containers (innermost repeated card, not an
        # ancestor wrapper that would duplicate every doctor's text into one blob).
        cards.sort(key=lambda c: len(c.find_all()))
        deduped = []
        seen_ids = set()
        for c in cards:
            if id(c) in seen_ids:
                continue
            # Drop any candidate that is an ancestor of an already-kept smaller card.
            if any(kept in c.find_all() for kept in deduped):
                continue
            deduped.append(c)
            seen_ids.add(id(c))
        return deduped[:MAX_DOCTORS]

    # Fallback: repeating heading + nearby text, when there's no clear card wrapper.
    fallback = []
    for heading in soup.find_all(re.compile(r"^h[2-4]$")):
        text_block = heading.get_text(" ", strip=True)
        sib_text = ""
        node = heading.find_next_sibling()
        hops = 0
        while node is not None and hops < 3:
            sib_text += " " + node.get_text(" ", strip=True)
            node = node.find_next_sibling()
            hops += 1
        combined = f"{text_block} {sib_text}"
        if QUALIFICATION_RE.search(combined):
            fallback.append((heading, combined))
        if len(fallback) >= MAX_DOCTORS:
            break
    return fallback


def _extract_doctor_from_card(card, page_url: str) -> Optional[dict]:
    is_tuple_fallback = isinstance(card, tuple)
    if is_tuple_fallback:
        heading, text_block = card
        name = heading.get_text(strip=True)
        img = None
    else:
        heading = card.find(re.compile(r"^h[1-6]$")) or card.find(["strong", "b"])
        name = heading.get_text(strip=True) if heading else ""
        img = card.find("img")
        text_block = card.get_text(" ", strip=True)

    name = re.sub(r"^(Dr\.?\s*)?", "", name).strip()
    # Real names don't contain digits/parens/newlines or run past a handful of words —
    # cheap filter for nav/widget clutter ("Meet our Experts (3281)") that otherwise
    # matches the same CSS classes as an actual doctor card on JS-heavy corporate sites.
    if not name or len(name) < 3 or len(name) > 60 or len(name.split()) > 6:
        return None
    if re.search(r"[\d()\n]", name):
        return None
    name = f"Dr. {name}"

    photo_url = _resolve_image_src(img, page_url) if img is not None else None
    if photo_url and (any(hint in photo_url.lower() for hint in _SKIP_IMAGE_HINTS) or photo_url.lower().endswith(".svg")):
        photo_url = None  # site logo / placeholder mistakenly picked up as the card's <img>, not a real doctor photo
    qualifications = ", ".join(sorted(set(m.upper() for m in QUALIFICATION_RE.findall(text_block))))
    experience_match = EXPERIENCE_RE.search(text_block)
    phone_match = PHONE_RE.search(text_block)
    email_match = EMAIL_RE.search(text_block)

    # Require at least one strong doctor-specific signal beyond "name + some image" —
    # otherwise this is more likely a nav item or unrelated card sharing the same class.
    if not qualifications and not experience_match and not phone_match and not email_match:
        return None

    specialty = ""
    if not is_tuple_fallback:
        spec_el = card.find(class_=re.compile(r"(specialt|designation|department|role|position)", re.IGNORECASE))
        if spec_el:
            specialty = spec_el.get_text(strip=True)
    if not specialty:
        # Best-effort: text right after the name, before qualifications/experience noise.
        after_name = text_block.split(name.replace("Dr. ", ""), 1)
        remainder = after_name[1].strip(" -|,") if len(after_name) > 1 else ""
        specialty = remainder[:100].split(".")[0].strip()

    return {
        "name": name,
        "photo_url": photo_url,
        "photo_status": "found" if photo_url else "missing",
        "specialty": specialty[:290] if specialty else None,
        "qualifications": qualifications[:490] if qualifications else None,
        "experience": experience_match.group(1) if experience_match else None,
        "phone": phone_match.group(0) if phone_match else None,
        "email": email_match.group(0) if email_match else None,
        "source_url": page_url,
        "raw_text": text_block[:800],
    }


def extract_doctors(doctors_url: str) -> list:
    resp = _get(doctors_url)
    if resp is None:
        return []
    soup = _soup(resp)
    cards = _find_doctor_cards(soup)
    doctors, seen_names = [], set()
    for card in cards:
        doctor = _extract_doctor_from_card(card, resp.url)
        if doctor is None:
            continue
        key = doctor["name"].lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        doctors.append(doctor)
    return doctors


# ─── Orchestration ─────────────────────────────────────────────────────────────

class EnrichmentResult:
    __slots__ = ("website_url", "website_status", "website_match_confidence",
                 "gallery_status", "gallery_images",
                 "doctors_page_url", "doctors_page_status", "doctors",
                 "overall_status", "error_detail")

    def __init__(self):
        self.website_url = None
        self.website_status = "pending"
        self.website_match_confidence = None
        self.gallery_status = "pending"
        self.gallery_images = []
        self.doctors_page_url = None
        self.doctors_page_status = "pending"
        self.doctors = []
        self.overall_status = "pending"
        self.error_detail = None


def enrich_listing(name: str, city: str, jd_url: Optional[str], search_page=None) -> EnrichmentResult:
    """Runs the full pipeline for one hospital and returns the outcome. Never raises —
    every failure path is captured on the result so the caller can persist it.
    `search_page` is an optional Playwright Page (see search_candidates) used only for
    the website-discovery step; when None, listings without an existing website simply
    resolve to website_status="not_found" instead of attempting a search."""
    result = EnrichmentResult()

    class _L:  # tiny shim so existing_website_candidate can take either a Listing or plain args
        pass
    listing_shim = _L()
    listing_shim.jd_url = jd_url

    website = existing_website_candidate(listing_shim)
    if website:
        result.website_url = website
        result.website_status = "found_existing"
        result.website_match_confidence = 1.0
    else:
        try:
            candidates = search_candidates(search_page, name, city)
            best_url, score = pick_best_website(candidates, name, city)
        except Exception as e:
            result.website_status = "failed"
            result.overall_status = "failed"
            result.error_detail = f"Website search failed: {e}"
            return result
        if best_url:
            result.website_url = best_url
            result.website_status = "found_via_search"
            result.website_match_confidence = score
        else:
            result.website_status = "not_found"

    if not result.website_url:
        result.gallery_status = "skipped_no_website"
        result.doctors_page_status = "skipped_no_website"
        result.overall_status = "failed"
        result.error_detail = "No official website could be found or confidently matched"
        return result

    home_resp = _get(result.website_url)
    if home_resp is None:
        result.gallery_status = "failed"
        result.doctors_page_status = "failed"
        result.overall_status = "failed"
        result.error_detail = f"Website unreachable: {result.website_url}"
        return result
    home_url = home_resp.url
    result.website_url = home_url
    home_soup = _soup(home_resp)

    try:
        gallery_url = find_gallery_page(home_url, home_soup)
        images = extract_gallery_images(gallery_url, home_soup, home_url)
        result.gallery_images = images
        result.gallery_status = "found" if images else "not_found"
    except Exception as e:
        result.gallery_status = "failed"
        result.error_detail = f"Gallery extraction error: {e}"

    try:
        doctors_url = find_doctors_page(home_url, home_soup)
        if doctors_url:
            doctors = extract_doctors(doctors_url)
            result.doctors_page_url = doctors_url
            result.doctors = doctors
            result.doctors_page_status = "found" if doctors else "found_but_empty"
        else:
            result.doctors_page_status = "not_found"
    except Exception as e:
        result.doctors_page_status = "failed"
        prior = f"{result.error_detail}; " if result.error_detail else ""
        result.error_detail = f"{prior}Doctors page extraction error: {e}"

    if result.gallery_status == "found" and result.doctors_page_status == "found":
        result.overall_status = "completed"
    elif result.gallery_status == "failed" and result.doctors_page_status == "failed":
        result.overall_status = "failed"
        result.error_detail = result.error_detail or "Both gallery and doctors extraction failed"
    else:
        result.overall_status = "completed_partial"

    return result
