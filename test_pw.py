import asyncio, json
from playwright.async_api import async_playwright

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        async def handle_response(response):
            try:
                if 'justdial.com' in response.url and 'api' in response.url.lower():
                    print("API CALL:", response.url)
            except Exception:
                pass

        page.on("response", handle_response)
        
        base_url = "https://www.justdial.com/Kasaragod/Restaurants/nct-10408936"
        print("Loading page 1")
        await page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        print("Scrolling...")
        for _ in range(5):
            await page.mouse.wheel(0, 1000)
            await page.wait_for_timeout(1000)
        
        await browser.close()
        print("Done")

asyncio.run(scrape())
