
import asyncio
import re
import os
from typing import List, Dict, Optional, Tuple
from playwright.async_api import async_playwright, Page, Browser
import httpx

def get_gallery_url(place_url: str) -> Optional[str]:
    """
    Converts a Google Maps place URL to a photo gallery URL
    """
    if "/maps/place/" not in place_url:
        return None
    base_url = place_url.split("?")[0]
    return base_url + "/photos?hl=en"

def to_highres_url(img_url: str) -> str:
    """
    Modifies Google Maps image URL to get maximum resolution (4096x4096)
    """
    # Remove any existing size parameters
    cleaned = re.sub(r"=(w\d+|h\d+|s\d+|w\d+-h\d+|p-k-no).*$", "", img_url)
    # Add max resolution params
    return cleaned + "=w4096-h4096-k-no"

async def extract_highres_images(
    page: Page,
    place_url: str,
    max_images: int = 50,
    scroll_rounds: int = 80
) -> Tuple[List[str], str]:
    """
    Extracts high-resolution image URLs from a Google Maps place
    Handles both direct place URLs and search result URLs
    """
    highres_urls: List[str] = []
    place_name = "Unknown Place"
    
    try:
        # Navigate to the provided URL first
        await page.goto(place_url, wait_until="commit", timeout=30000)
        await page.wait_for_timeout(2000)
        
        # Check if this is a search results page (not a specific place)
        # If yes, click the first result
        if "/maps/search/" in place_url or "/maps/place/" not in place_url:
            # Try to click the first search result
            try:
                # Wait for results to load
                await page.wait_for_timeout(3000)
                
                # Try a few common selectors for the first result
                first_result_selectors = [
                    "div[role='article']",
                    "a[href*='/maps/place/']",
                    "div.Nv2PK"  # Common Google Maps result container
                ]
                
                for selector in first_result_selectors:
                    try:
                        el = await page.query_selector(selector)
                        if el:
                            await el.click()
                            await page.wait_for_timeout(3000)
                            break
                    except:
                        continue
            except Exception as e:
                print(f"Could not click first search result: {e}")
        
        # Now try to navigate to the gallery (if we're on a place page)
        current_url = page.url
        gallery_url = get_gallery_url(current_url)
        if gallery_url:
            await page.goto(gallery_url, wait_until="commit", timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Extract place name
            name_el = await page.query_selector("h1.DUwDvf")
            if name_el:
                place_name = (await name_el.inner_text()).strip()
        
        # Scroll to load all images
        prev_count = 0
        stale_rounds = 0
        for _ in range(scroll_rounds):
            try:
                # Scroll all relevant containers
                await page.evaluate("""
                    () => {
                        let didScroll = false;
                        let divs = Array.from(document.querySelectorAll('div'));
                        for (let d of divs) {
                            let style = window.getComputedStyle(d);
                            if ((style.overflowY === 'auto' || style.overflowY === 'scroll')
                                && d.scrollHeight > d.clientHeight + 50) {
                                let imgs = d.querySelectorAll('img, [data-src]');
                                let hasGmaps = false;
                                for (let img of imgs) {
                                    let s = img.src || img.getAttribute('data-src') || '';
                                    if (s.includes('googleusercontent') || s.includes('ggpht')) {
                                        hasGmaps = true;
                                        break;
                                    }
                                }
                                if (hasGmaps || imgs.length > 5) {
                                    d.scrollTop = d.scrollHeight;
                                    didScroll = true;
                                }
                            }
                        }
                        if (!didScroll) {
                            window.scrollBy(0, 1500);
                        }
                        return didScroll;
                    }
                """)
                await page.wait_for_timeout(400)
                
                # Count images
                cur_count = await page.evaluate("""
                    () => {
                        let count = 0;
                        Array.from(document.querySelectorAll('img, [data-src]')).forEach(el => {
                            let s = el.getAttribute('data-src') || el.src || '';
                            if ((s.includes('googleusercontent') || s.includes('ggpht'))
                                && !s.includes('w32-h32') && !s.includes('w48-h48')
                                && !s.includes('w64-h64') && !s.includes('w20-h20')) {
                                count++;
                            }
                        });
                        return count;
                    }
                """)
                
                if cur_count == prev_count:
                    stale_rounds += 1
                    if stale_rounds >= 8:
                        break
                else:
                    stale_rounds = 0
                    prev_count = cur_count
            except Exception:
                break
        
        # Extract all image URLs
        raw_urls: List[str] = await page.evaluate("""
            () => {
                let results = [];
                // 1. img tags with src/data-src
                document.querySelectorAll('img, [data-src]').forEach(el => {
                    let s = el.getAttribute('data-src') || el.src || '';
                    if (s && (s.includes('googleusercontent') || s.includes('ggpht'))) {
                        results.push(s);
                    }
                });
                // 2. Background images
                document.querySelectorAll('[style*="googleusercontent"], [style*="ggpht"]').forEach(el => {
                    let style = el.getAttribute('style') || '';
                    try {
                        Array.from(style.matchAll(/url\\("?([^"')]+(?:googleusercontent|ggpht)[^"')]+)"?\\)/g))
                            .forEach(m => results.push(m[1]));
                    } catch(e) {}
                });
                // 3. srcset
                document.querySelectorAll('img[srcset]').forEach(img => {
                    let srcset = img.getAttribute('srcset') || '';
                    srcset.split(',').forEach(part => {
                        let url = part.trim().split(' ')[0];
                        if (url && (url.includes('googleusercontent') || url.includes('ggpht'))) {
                            results.push(url);
                        }
                    });
                });
                return results;
            }
        """)
        
        # Deduplicate and convert to high-res
        seen = set()
        for url in raw_urls:
            if len(highres_urls) >= max_images:
                break
            # Skip small thumbnails and avatars
            if any(sz in url for sz in ['w32-h32', 'w48-h48', 'w64-h64', 'w20-h20', 'w34-h34', 'w200-h200', 'w16-h16', 'w24-h24', 'p-k-no', 'w40-h40', 'w56-h56']):
                continue
            if '/a/' in url and '=s' in url:
                continue
            # Canonicalize
            canonical = re.sub(r"=(w\d+|h\d+|s\d+|w\d+-h\d+).*$", "", url)
            if canonical not in seen:
                seen.add(canonical)
                highres_urls.append(to_highres_url(canonical))
        
        return highres_urls, place_name
    
    except Exception as e:
        print(f"Error extracting images: {e}")
        return highres_urls, place_name

async def download_images_async(
    image_urls: List[str],
    output_dir: str,
    place_name: str,
    parallel: int = 10
) -> List[str]:
    """
    Downloads images in parallel using httpx
    """
    # Sanitize place name for directory
    safe_name = re.sub(r'[^\w\-_\. ]', '_', place_name).strip()
    place_dir = os.path.join(output_dir, safe_name)
    os.makedirs(place_dir, exist_ok=True)
    
    downloaded_paths: List[str] = []
    
    # Semaphore to limit parallel downloads
    semaphore = asyncio.Semaphore(parallel)
    
    async def download_one(idx: int, url: str):
        async with semaphore:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, follow_redirects=True)
                    response.raise_for_status()
                    ext = ".jpg"
                    filename = f"{safe_name}_img_{idx+1}{ext}"
                    filepath = os.path.join(place_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    downloaded_paths.append(filepath)
            except Exception as e:
                print(f"Failed to download image {idx+1}: {e}")
    
    # Create tasks
    tasks = [download_one(i, url) for i, url in enumerate(image_urls)]
    await asyncio.gather(*tasks)
    
    return downloaded_paths
