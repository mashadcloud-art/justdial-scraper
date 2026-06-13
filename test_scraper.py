from app.scraper.desktop_scraper import scrape_city

if __name__ == "__main__":
    print("Testing scraper on Kochi with limit of 2 restaurants...")
    scrape_city('Kochi', max_limit=2)
