# Saved Commands & Conversation Log

*If the chat disconnects or resets, you can always find your important commands and recent project updates here!*

## AUDITORIUM KOCHI (Massive Automated Scraping)

Because JustDial caps results at around 30 per specific search, we built an entirely new automated script to bypass this and get 1000+ results.

### What We Did Today:
1. **Created a dedicated batch script:** `scrape_ernakulam_auditoriums.py`
2. **Added 8 Event Categories:** It automatically searches for "Banquet Halls", "Auditoriums", "Marriage Halls", "Kalyana Mandapams", "Convention Centers", "Party Halls", "Event Venues", and "Function Halls".
3. **Expanded the Map to 39 Locations:** We added all major Kochi neighborhoods so it scans every inch of the district, including:
   *Willingdon Island, Bolgatty, Vypeen, Chottanikkara, Koothattukulam, Kolenchery, Kizhakkambalam, Pothanicad, Maradu, Cheranallur, Eloor, Thammanam, Poonithura, Vennala, Kumbalam, Kundannoor, Edappally, Vyttila, Palarivattom, Kadavanthra, Panampilly Nagar, Kaloor, Marine Drive, Fort Kochi, Mattancherry, Thoppumpady, Palluruthy, Kochi, Ernakulam, Aluva, Angamaly, Perumbavoor, Muvattupuzha, Kothamangalam, Tripunithura, Kalamassery, Kakkanad, North Paravur, and Piravom.*
4. **Unlocked the Web UI:** We removed the security lock in the backend so you can run custom Python scripts directly from your web dashboard's "CLI Mode".

### How to Run This Massive Scrape Anytime:

**Option 1: In the Web Dashboard's "Power User (CLI Mode)" box:**
```bash
python scrape_ernakulam_auditoriums.py
```

**Option 2: Directly in Windows PowerShell / Command Prompt:**
*(Make sure you are inside your project folder first!)*
```powershell
C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe scrape_ernakulam_auditoriums.py
```

---

## 2. Standard Single-Category Scraping
If you want to run a simple, one-off scrape for a different district (like Kasaragod) using the standard scraper:

```bash
python jd_api_scraper.py --district Kasaragod --category "Banquet Halls" --pages 3 --limit 100
```
*(Note: We use 3 pages per area because JustDial usually doesn't have more than 300 banquet halls in a single tiny pincode area. By looping over all areas automatically, it collects them all.)*

---

## 3. How to Start the App on your Ubuntu Cloud Server (VPS)

If your live Streamlit dashboard (e.g., `http://129.151.146.44:8501/`) says the backend or listings aren't showing, it means the FastAPI backend isn't running on the server.

**Step 1: Go to your project folder**
```bash
cd "Scapre for thozil"
```

**Step 2: Force install requirements (Ubuntu 24.04 bypass)**
```bash
python3 -m pip install -r requirements.txt --break-system-packages
```

**Step 3: Start the FastAPI Backend**
```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
*(Once this is running, your live Streamlit dashboard will successfully connect and show all your scraped data!)*
