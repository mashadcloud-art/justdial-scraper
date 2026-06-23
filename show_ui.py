import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def show_user():
    print("Launching browser to show user...")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    
    # We will launch a visible browser on their actual desktop
    driver = uc.Chrome(options=options, version_main=149)
    
    print("Navigating to dashboard...")
    driver.get("http://localhost:8080/")
    
    time.sleep(2) # let react load
    
    try:
        print("Finding Engine dropdown...")
        # Find the dropdown that contains "Scraper Engine"
        # The label has text "Scraper Engine", the select is the next element
        # We can just look for the select element that has an option "emulator"
        select_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//select[option[@value='emulator']]"))
        )
        
        time.sleep(1)
        
        print("Selecting 'emulator'...")
        # Change the value via JS to trigger React
        driver.execute_script("arguments[0].value = 'emulator'; arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", select_element)
        
        time.sleep(2)
        
        print("Finding the JSON text area...")
        textarea = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//textarea[@placeholder='{\"results\": {\"columns\": [...], \"data\": [...]}}']"))
        )
        
        # Flash the textarea to draw attention
        for _ in range(3):
            driver.execute_script("arguments[0].style.border = '5px solid red'", textarea)
            time.sleep(0.5)
            driver.execute_script("arguments[0].style.border = ''", textarea)
            time.sleep(0.5)
            
        # Type a demonstration message
        textarea.send_keys("--> PASTE YOUR HTTP TOOLKIT JSON RIGHT HERE <--")
        
        print("Done. Leaving browser open for user.")
        
        # Keep it open for 30 seconds so they can see it
        time.sleep(30)
        
    except Exception as e:
        print(f"Error demonstrating UI: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    show_user()
