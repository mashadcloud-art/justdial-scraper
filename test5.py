import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        await page.goto("https://www.justdial.com/Idukki/Fast-Food", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        results = soup.find_all('div', class_='resultbox_info')
        print(f"Found {len(results)} resultbox_info elements")
        
        if len(results) == 0:
            print("Trying other common classes")
            # Justdial uses different classes sometimes, try finding generic names
            for el in soup.find_all(['h2', 'h3']):
                if el.text and len(el.text.strip()) > 3:
                    print("Heading:", el.text.strip())
                    
        with open("dump.html", "w", encoding="utf-8") as f:
            f.write(content)
            
        await browser.close()

asyncio.run(main())
