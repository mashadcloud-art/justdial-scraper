import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import os
import sys
import json
import requests
import webbrowser
import subprocess
from datetime import datetime
from tkinterweb import HtmlFrame

# Add project directory to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import our scraper functions
from app.scraper.desktop_scraper import (
    scrape_city,
    scrape_single_url,
    set_stop_flag
)
from app.scraper.category_fetcher import (
    fetch_categories_from_justdial,
    get_main_categories,
    get_subcategories
)

# ==================== INDIAN STATES & DISTRICTS ====================
INDIAN_STATES = {
    "Kerala": ["Thiruvananthapuram", "Kollam", "Pathanamthitta", "Alappuzha", "Kottayam", "Idukki", "Ernakulam", "Thrissur", "Palakkad", "Malappuram", "Kozhikode", "Wayanad", "Kannur", "Kasaragod"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tirunelveli", "Erode", "Vellore", "Tiruppur", "Dindigul"],
    "Karnataka": ["Bangalore", "Mysuru", "Mangaluru", "Hubli", "Belagavi", "Kalaburagi", "Davangere", "Shivamogga"],
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Tirupati", "Rajahmundry"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik", "Aurangabad", "Solapur"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Bikaner"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Agra", "Varanasi", "Meerut", "Prayagraj"],
    "Delhi": ["New Delhi", "North Delhi", "South Delhi", "East Delhi", "West Delhi"],
    "Haryana": ["Faridabad", "Gurugram", "Panipat", "Ambala", "Hisar"],
    "Punjab": ["Chandigarh", "Ludhiana", "Amritsar", "Jalandhar", "Patiala"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Gwalior", "Jabalpur"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Asansol"],
    "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur"]
}

# ==================== SCRAPER APPLICATION ====================
class ScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("JustDial Pro Scraper - Ultimate Version")
        self.root.geometry("1280x850")
        self.root.minsize(1000, 600)
        # Allow maximizing and resizing
        self.root.resizable(True, True)

        # Initialize state
        self.is_scraping = False
        self.categories = fetch_categories_from_justdial()
        self.fastapi_process = None

        # Create main container
        self.main_container = ttk.Frame(self.root, padding="12")
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # --------------------------
        # TOP: TABS
        # --------------------------
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        # Create tabs
        self.scraper_tab = ttk.Frame(self.notebook, padding="15")
        self.dashboard_tab = ttk.Frame(self.notebook, padding="15")
        self.url_tab = ttk.Frame(self.notebook, padding="15")
        self.browser_tab = ttk.Frame(self.notebook, padding="10")

        self.notebook.add(self.scraper_tab, text="🏙️ Scraper")
        self.notebook.add(self.dashboard_tab, text="📊 Dashboard")
        self.notebook.add(self.url_tab, text="🔗 Single URL")
        self.notebook.add(self.browser_tab, text="🌐 Browser")

        # --------------------------
        # BOTTOM: LOG
        # --------------------------
        self.log_frame = ttk.LabelFrame(self.main_container, text="📜 Activity Log", padding="8")
        self.log_frame.pack(fill=tk.X, expand=False)

        self.log_text = scrolledtext.ScrolledText(
            self.log_frame,
            wrap=tk.WORD,
            height=9,
            font=("Consolas", 9),
            background="#1a1a2e",
            foreground="#00ff00"
        )
        self.log_text.pack(fill=tk.X, expand=True)

        # Store full JD URLs for lookup
        self.jd_urls = {}

        # Clean up on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Check if FastAPI is running, start if not
        self.check_fastapi_running()

        # Setup each tab
        self.setup_scraper_tab()
        self.setup_dashboard_tab()
        self.setup_url_tab()
        self.setup_browser_tab()

    def check_fastapi_running(self):
        """Check if FastAPI server is running, start it automatically if not"""
        # First check if it's already running
        try:
            response = requests.get("http://localhost:8000/", timeout=3)
            if response.status_code == 200:
                self.log("✅ FastAPI server is already running!")
                return True
        except Exception:
            pass
        
        # Not running, start it ourselves!
        self.log("🔄 Starting FastAPI server in background...")
        
        # Get Python path and project dir
        python_path = r"C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe"
        
        # Start FastAPI in hidden mode (no terminal window!)
        self.fastapi_process = subprocess.Popen(
            [python_path, "-m", "uvicorn", "app.main:app", "--host", "localhost", "--port", "8000"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW  # No terminal window on Windows!
        )
        
        # Wait a bit for server to start
        import time
        time.sleep(5)
        
        # Verify it started
        try:
            response = requests.get("http://localhost:8000/", timeout=5)
            if response.status_code == 200:
                self.log("✅ FastAPI server started successfully!")
                return True
        except Exception:
            pass
        
        self.log("⚠️  Failed to start FastAPI server!")
        messagebox.showwarning(
            "Server Start Failed",
            "Could not start FastAPI server automatically!\n\nPlease check your Python installation!"
        )
        return False

    def on_close(self):
        """Clean up and close the app"""
        if self.fastapi_process:
            try:
                self.fastapi_process.terminate()
                self.log("✅ FastAPI server stopped!")
            except Exception:
                pass
        self.root.destroy()

    def log(self, message):
        """Thread-safe logging"""
        if not hasattr(self, 'log_text') or not self.log_text:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
        except Exception:
            pass

    # ==================== SCRAPER TAB ====================
    def setup_scraper_tab(self):
        """Setup the main scraper tab"""
        # Title row
        title_frame = ttk.Frame(self.scraper_tab)
        title_frame.pack(fill=tk.X, pady=(0, 18))
        ttk.Label(title_frame, text="Location & Category Scraper", font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)

        # Main content - 3 columns
        content_frame = ttk.Frame(self.scraper_tab)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # COLUMN 1: LOCATION
        location_frame = ttk.LabelFrame(content_frame, text="📍 Location Settings", padding="15")
        location_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # State
        ttk.Label(location_frame, text="State / UT:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 6))
        self.state_var = tk.StringVar()
        self.state_combo = ttk.Combobox(
            location_frame,
            textvariable=self.state_var,
            values=list(INDIAN_STATES.keys()),
            state="readonly",
            width=28
        )
        self.state_combo.current(0)
        self.state_combo.grid(row=1, column=0, sticky=tk.EW, pady=(0, 15))
        self.state_combo.bind('<<ComboboxSelected>>', self.on_state_change)

        # District
        ttk.Label(location_frame, text="District / City:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=(0, 6))
        self.district_var = tk.StringVar()
        self.district_combo = ttk.Combobox(
            location_frame,
            textvariable=self.district_var,
            values=INDIAN_STATES["Kerala"],
            state="readonly",
            width=28
        )
        self.district_combo.current(6)  # Ernakulam
        self.district_combo.grid(row=3, column=0, sticky=tk.EW, pady=(0, 15))

        # Max businesses
        ttk.Label(location_frame, text="Max Entries (0=All):", font=("Segoe UI", 10, "bold")).grid(row=4, column=0, sticky=tk.W, pady=(0, 6))
        max_frame = ttk.Frame(location_frame)
        max_frame.grid(row=5, column=0, sticky=tk.EW)
        self.max_var = tk.IntVar(value=10)
        max_spin = ttk.Spinbox(max_frame, from_=0, to=1000, textvariable=self.max_var, width=25)
        max_spin.pack(side=tk.LEFT)

        # COLUMN 2: CATEGORIES
        category_frame = ttk.LabelFrame(content_frame, text="📂 Category Selection", padding="15")
        category_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 10))

        # Main category
        ttk.Label(category_frame, text="Main Category:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 6))
        self.main_cat_var = tk.StringVar()
        self.main_cat_combo = ttk.Combobox(
            category_frame,
            textvariable=self.main_cat_var,
            values=list(self.categories.keys()),
            state="readonly",
            width=28
        )
        self.main_cat_combo.current(7)  # Hotels & Restaurants
        self.main_cat_combo.grid(row=1, column=0, sticky=tk.EW, pady=(0, 15))
        self.main_cat_combo.bind('<<ComboboxSelected>>', self.on_main_cat_change)

        # Subcategory
        ttk.Label(category_frame, text="Subcategory (Optional):", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=(0, 6))
        self.subcat_var = tk.StringVar()
        self.subcat_combo = ttk.Combobox(
            category_frame,
            textvariable=self.subcat_var,
            values=self.categories.get("Hotels & Restaurants", {}).get("subcategories", []),
            state="readonly",
            width=28
        )
        self.subcat_combo.set("Restaurants")  # Default
        self.subcat_combo.grid(row=3, column=0, sticky=tk.EW, pady=(0, 15))

        # Refresh categories
        ttk.Button(category_frame, text="🔄 Refresh Categories", command=self.refresh_categories).grid(row=4, column=0, sticky=tk.EW)

        # COLUMN 3: CONTROLS
        control_frame = ttk.LabelFrame(content_frame, text="🎮 Scraper Controls", padding="15")
        control_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # Status indicator
        self.status_label = ttk.Label(control_frame, text="Status: Ready", font=("Segoe UI", 10), foreground="#0078d4")
        self.status_label.pack(anchor=tk.W, pady=(0, 18))

        # Buttons
        self.start_btn = ttk.Button(
            control_frame,
            text="🚀 START SCRAPING",
            command=self.start_scrape
        )
        self.start_btn.pack(fill=tk.X, pady=(0, 10))

        self.stop_btn = ttk.Button(
            control_frame,
            text="🛑 STOP SCRAPING",
            command=self.stop_scrape,
            state=tk.DISABLED
        )
        self.stop_btn.pack(fill=tk.X, pady=(0, 15))

        ttk.Button(
            control_frame,
            text="Clear Log",
            command=lambda: self.log_text.delete(1.0, tk.END)
        ).pack(fill=tk.X)

        # Info text
        info_frame = ttk.LabelFrame(self.scraper_tab, text="💡 Quick Tips", padding="12")
        info_frame.pack(fill=tk.X, pady=(15, 0))

        info = """• Solve CAPTCHA when Chrome opens - scraper will auto-detect page load
• Click STOP button to cancel immediately
• Check Dashboard to view results
• Categories are cached for future use"""
        ttk.Label(info_frame, text=info, justify=tk.LEFT, font=("Segoe UI", 9)).pack(anchor=tk.W)

    def on_state_change(self, event):
        selected_state = self.state_var.get()
        self.district_combo['values'] = INDIAN_STATES.get(selected_state, [])
        self.district_combo.current(0)

    def on_main_cat_change(self, event):
        main_cat = self.main_cat_var.get()
        subcats = self.categories.get(main_cat, {}).get("subcategories", [])
        self.subcat_combo['values'] = subcats
        if subcats:
            self.subcat_combo.current(0)

    def refresh_categories(self):
        """Refresh categories from JustDial"""
        self.log("🔄 Refreshing categories...")
        self.categories = fetch_categories_from_justdial()
        self.main_cat_combo['values'] = list(self.categories.keys())
        self.log("✅ Categories updated!")

    # ==================== DASHBOARD TAB ====================
    def setup_dashboard_tab(self):
        """Setup dashboard"""
        title_frame = ttk.Frame(self.dashboard_tab)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(title_frame, text="Scraped Results Dashboard", font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)

        # Stats
        stats_frame = ttk.Frame(self.dashboard_tab)
        stats_frame.pack(fill=tk.X, pady=(0, 15))

        self.stat_labels = {}
        for name, initial in [("Total Businesses", "0"), ("Images", "0"), ("Menu Items", "0")]:
            frame = ttk.Frame(stats_frame)
            frame.pack(side=tk.LEFT, padx=(0, 35))
            ttk.Label(frame, text=name, font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
            self.stat_labels[name] = ttk.Label(frame, text=initial, font=("Segoe UI", 26, "bold"), foreground="#0078d4")
            self.stat_labels[name].pack(anchor=tk.W)

        # Refresh button
        btn_frame = ttk.Frame(self.dashboard_tab)
        btn_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Button(btn_frame, text="🔄 Refresh Dashboard", command=self.refresh_dashboard).pack(side=tk.LEFT)

        # Table
        tree_frame = ttk.LabelFrame(self.dashboard_tab, text="📋 Business List", padding="10")
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("Name", "Category", "Phone", "WhatsApp", "Address", "JustDial Link")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=16)
        for col in columns:
            self.tree.heading(col, text=col)
            if col == "JustDial Link":
                self.tree.column(col, width=250)
            elif col == "Address":
                self.tree.column(col, width=200)
            elif col == "Name":
                self.tree.column(col, width=180)
            else:
                self.tree.column(col, width=120)

        # Bind double-click to open JD link
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.refresh_dashboard()

    def refresh_dashboard(self):
        """Refresh dashboard from API"""
        try:
            # Clear tree
            for item in self.tree.get_children():
                self.tree.delete(item)

            # Get stats
            stats_resp = requests.get("http://localhost:8000/api/v1/stats", timeout=3)
            if stats_resp.ok:
                stats = stats_resp.json()
                self.stat_labels["Total Businesses"].config(text=str(stats.get("total_restaurants", 0)))
                self.stat_labels["Images"].config(text=str(stats.get("total_images", 0)))
                self.stat_labels["Menu Items"].config(text=str(stats.get("total_menu_items", 0)))

            # Clear stored URLs
            self.jd_urls = {}

            # Get businesses
            rest_resp = requests.get("http://localhost:8000/api/v1/restaurants", timeout=5)
            if rest_resp.ok:
                for r in rest_resp.json():
                    # Insert into tree and store full URL
                    item_id = self.tree.insert("", tk.END, values=(
                        r.get("name", "")[:40],
                        r.get("category", "")[:30],
                        r.get("phone", ""),
                        r.get("whatsapp", ""),
                        r.get("address", "")[:40],
                        r.get("jd_url", "")[:50]  # Truncate long links
                    ))
                    if r.get("jd_url"):
                        self.jd_urls[item_id] = r["jd_url"]

            self.log("✅ Dashboard refreshed!")

        except Exception as e:
            self.log(f"⚠️  API connection failed: {str(e)}")

    def on_tree_double_click(self, event):
        """Handle double-click to open JD link"""
        selection = self.tree.selection()
        if selection:
            item_id = selection[0]
            if item_id in self.jd_urls:
                url = self.jd_urls[item_id]
                self.browser_url.set(url)
                self.browser_frame.load_website(url)
                self.notebook.select(self.browser_tab)

    # ==================== URL TAB ====================
    def setup_url_tab(self):
        """Setup single URL tab"""
        title_frame = ttk.Frame(self.url_tab)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(title_frame, text="Single URL Scraper", font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)

        url_frame = ttk.LabelFrame(self.url_tab, text="🔗 JustDial URL", padding="15")
        url_frame.pack(fill=tk.X, pady=(0, 15))

        self.url_var = tk.StringVar()
        entry = ttk.Entry(url_frame, textvariable=self.url_var, font=("Segoe UI", 10))
        entry.pack(fill=tk.X, pady=(0, 10))

        btn_frame = ttk.Frame(url_frame)
        btn_frame.pack(fill=tk.X)
        self.url_start_btn = ttk.Button(btn_frame, text="🚀 Scrape This URL", command=self.start_url_scrape)
        self.url_start_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="Clear Log", command=lambda: self.log_text.delete(1.0, tk.END)).pack(side=tk.LEFT)

        example = ttk.Label(self.url_tab, text="Example: https://www.justdial.com/Kochi/Restaurant-Name...", foreground="#666")
        example.pack(anchor=tk.W)

    def setup_browser_tab(self):
        """Setup embedded browser tab"""
        # URL controls
        control_frame = ttk.Frame(self.browser_tab)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        # Back and forward buttons
        ttk.Button(control_frame, text="◀ Back", command=self.browser_back).pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(control_frame, text="▶ Forward", command=self.browser_forward).pack(side=tk.LEFT, padx=(0,5))

        # URL entry
        self.browser_url = tk.StringVar(value="https://www.google.com")
        url_entry = ttk.Entry(control_frame, textvariable=self.browser_url, font=("Segoe UI",10))
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        url_entry.bind("<Return>", lambda e: self.browser_go())

        # Go button
        ttk.Button(control_frame, text="🔍 Go", command=self.browser_go).pack(side=tk.LEFT)

        # Embedded browser
        self.browser_frame = HtmlFrame(self.browser_tab, messages_enabled=False)
        self.browser_frame.pack(fill=tk.BOTH, expand=True)

        # Load initial page
        self.browser_frame.load_website(self.browser_url.get())

    def browser_go(self):
        url = self.browser_url.get().strip()
        if url:
            if not url.startswith("http"):
                url = "https://" + url
                self.browser_url.set(url)
            self.browser_frame.load_website(url)

    def browser_back(self):
        self.browser_frame.back()

    def browser_forward(self):
        self.browser_frame.forward()

    # ==================== SCRAPING CONTROLS ====================
    def start_scrape(self):
        """Start scraping"""
        if self.is_scraping:
            return

        district = self.district_var.get()
        if not district:
            messagebox.showwarning("Warning", "Please select a district!")
            return

        self.is_scraping = True
        set_stop_flag(False)
        self.status_label.config(text="Status: Scraping...", foreground="#ff6600")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.url_start_btn.config(state=tk.DISABLED)

        main_cat = self.main_cat_var.get()
        subcat = self.subcat_var.get()
        max_rest = self.max_var.get()

        thread = threading.Thread(
            target=self.run_scrape,
            args=(district, main_cat, subcat, max_rest)
        )
        thread.daemon = True
        thread.start()

    def stop_scrape(self):
        """Stop scraping instantly"""
        set_stop_flag(True)
        self.log("🛑 STOP command sent!")

    def run_scrape(self, district, main_cat, subcat, max_rest):
        """Run scraping"""
        try:
            self.log(f"🚀 Starting scrape: {district} | {main_cat}{' / ' + subcat if subcat else ''}")

            # Redirect stdout
            original_stdout = sys.stdout
            class LogRedirector:
                def __init__(self, app):
                    self.app = app
                def write(self, text):
                    if text.strip():
                        self.app.log(text.rstrip())
                def flush(self):
                    pass

            sys.stdout = LogRedirector(self)

            scrape_city(district, main_cat, subcat, max_limit=max_rest)

            sys.stdout = original_stdout
            self.log("✅ Scrape complete!")
            self.refresh_dashboard()

        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
        finally:
            self.is_scraping = False
            set_stop_flag(False)
            self.status_label.config(text="Status: Ready", foreground="#0078d4")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.url_start_btn.config(state=tk.NORMAL)

    def start_url_scrape(self):
        """Start URL scraping"""
        if self.is_scraping:
            return

        url = self.url_var.get().strip()
        if not url or "justdial.com" not in url:
            messagebox.showwarning("Warning", "Enter valid JustDial URL!")
            return

        self.is_scraping = True
        set_stop_flag(False)
        self.start_btn.config(state=tk.DISABLED)
        self.url_start_btn.config(state=tk.DISABLED)

        thread = threading.Thread(target=self.run_url_scrape, args=(url,))
        thread.daemon = True
        thread.start()

    def run_url_scrape(self, url):
        """Run URL scrape"""
        try:
            self.log(f"🚀 Scraping URL...")

            original_stdout = sys.stdout
            class LogRedirector:
                def __init__(self, app):
                    self.app = app
                def write(self, text):
                    if text.strip():
                        self.app.log(text.rstrip())
                def flush(self):
                    pass

            sys.stdout = LogRedirector(self)
            success = scrape_single_url(url)
            sys.stdout = original_stdout

            if success:
                self.log("✅ Done!")
                self.refresh_dashboard()
            else:
                self.log("❌ Failed to scrape!")

        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
        finally:
            self.is_scraping = False
            set_stop_flag(False)
            self.start_btn.config(state=tk.NORMAL)
            self.url_start_btn.config(state=tk.NORMAL)

def main():
    root = tk.Tk()
    app = ScraperApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
