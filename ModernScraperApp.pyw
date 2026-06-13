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
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk

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

# ==================== MODERN SCRAPER APP ====================
class ModernScraperApp(tb.Window):
    def __init__(self):
        super().__init__(themename="superhero")
        self.title("JustDial Pro Scraper - v2.0")
        self.geometry("1500x1000")
        self.minsize(1200, 800)

        # Initialize state
        self.is_scraping = False
        self.categories = fetch_categories_from_justdial()
        self.fastapi_process = None
        self.all_businesses = []  # Store full business data locally
        self.photo_images = []  # Keep references to prevent garbage collection

        # Style
        style = tb.Style()
        style.configure("Treeview", font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))

        # Create main container
        self.main_container = tb.Frame(self, padding=15)
        self.main_container.pack(fill=BOTH, expand=True)

        # Header
        header_frame = tb.Frame(self.main_container)
        header_frame.pack(fill=X, pady=(0, 20))
        tb.Label(header_frame, text="JustDial Pro Scraper", font=("Segoe UI", 24, "bold"), foreground="#ffffff").pack(side=LEFT)

        # Notebook Tabs
        self.notebook = tb.Notebook(self.main_container)
        self.notebook.pack(fill=BOTH, expand=True, pady=(0, 10))

        # Create tabs
        self.setup_scraper_tab()
        self.setup_dashboard_tab()

        # Footer Log
        self.setup_log()

        # Clean up on window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Check/Start FastAPI
        self.check_fastapi_running()

    def check_fastapi_running(self):
        """Check if FastAPI is running; start it if not"""
        try:
            response = requests.get("http://localhost:8000/", timeout=3)
            if response.status_code == 200:
                self.log("✅ FastAPI server already running!")
                return True
        except Exception:
            pass

        # Not running, start it
        self.log("🚀 Starting FastAPI server in background...")
        python_path = r"C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe"
        self.fastapi_process = subprocess.Popen(
            [python_path, "-m", "uvicorn", "app.main:app", "--host", "localhost", "--port", "8000"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        import time
        time.sleep(5)
        try:
            response = requests.get("http://localhost:8000/", timeout=5)
            if response.status_code == 200:
                self.log("✅ FastAPI server started successfully!")
                return True
        except Exception:
            pass

        self.log("⚠️  FastAPI server failed to start automatically!")
        return False

    def setup_scraper_tab(self):
        tab = tb.Frame(self.notebook, padding=20)
        self.notebook.add(tab, text="🏙️ Scraper")

        # Two-column layout
        left_col = tb.Frame(tab)
        left_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))

        right_col = tb.Frame(tab)
        right_col.pack(side=RIGHT, fill=BOTH, expand=True, padx=(10, 0))

        # Left column - Location & Category
        left_frame = left_col
        
        # Right column - Controls & Single URL
        right_frame = right_col

        # ------------------ Left Section ------------------
        tb.Label(left_frame, text="📍 Location & Category", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0, 15))

        # State
        tb.Label(left_frame, text="State / UT:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 5))
        self.state_var = tb.StringVar()
        self.state_combo = tb.Combobox(left_frame, textvariable=self.state_var, values=list(INDIAN_STATES.keys()), state="readonly")
        self.state_combo.current(0)
        self.state_combo.pack(fill=X, pady=(0, 15))
        self.state_combo.bind("<<ComboboxSelected>>", self.on_state_change)

        # District
        tb.Label(left_frame, text="District / City:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 5))
        self.district_var = tb.StringVar()
        self.district_combo = tb.Combobox(left_frame, textvariable=self.district_var, values=INDIAN_STATES["Kerala"], state="readonly")
        self.district_combo.current(6)
        self.district_combo.pack(fill=X, pady=(0, 15))

        # Category
        tb.Label(left_frame, text="Main Category:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 5))
        self.main_cat_var = tb.StringVar()
        self.main_cat_combo = tb.Combobox(left_frame, textvariable=self.main_cat_var, values=list(self.categories.keys()), state="readonly")
        self.main_cat_combo.current(7)
        self.main_cat_combo.pack(fill=X, pady=(0, 15))
        self.main_cat_combo.bind("<<ComboboxSelected>>", self.on_main_cat_change)

        # Subcategory
        tb.Label(left_frame, text="Subcategory:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 5))
        self.subcat_var = tb.StringVar()
        self.subcat_combo = tb.Combobox(left_frame, textvariable=self.subcat_var, values=self.categories.get("Hotels & Restaurants", {}).get("subcategories", []), state="readonly")
        self.subcat_combo.set("Restaurants")
        self.subcat_combo.pack(fill=X, pady=(0, 15))

        # Max entries
        tb.Label(left_frame, text="Max Entries:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 5))
        max_frame = tb.Frame(left_frame)
        max_frame.pack(fill=X)
        self.max_var = tb.IntVar(value=10)
        tb.Spinbox(max_frame, from_=0, to=500, textvariable=self.max_var, width=20, font=("Segoe UI", 10)).pack(side=LEFT)

        # ------------------ Right Section ------------------
        # Top: Controls
        controls_container = tb.Frame(right_frame)
        controls_container.pack(fill=BOTH, expand=True, pady=(0, 20))

        tb.Label(controls_container, text="🎮 Controls", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0, 15))

        self.status_label = tb.Label(controls_container, text="Status: Ready", font=("Segoe UI", 12, "bold"), foreground="#2ecc71")
        self.status_label.pack(anchor=W, pady=(0, 20))

        self.start_btn = tb.Button(controls_container, text="🚀 Start Scraping", command=self.start_scrape, bootstyle="success")
        self.start_btn.pack(fill=X, pady=(0, 10))

        self.stop_btn = tb.Button(controls_container, text="🛑 Stop Scraping", command=self.stop_scrape, bootstyle="danger", state=DISABLED)
        self.stop_btn.pack(fill=X, pady=(0, 10))

        tb.Button(controls_container, text="🔄 Refresh Categories", command=self.refresh_categories, bootstyle="info").pack(fill=X, pady=(0, 20))

        # Bottom: Single URL Scraper
        tb.Separator(right_frame).pack(fill=X, pady=(20, 20))

        tb.Label(right_frame, text="🔗 Single URL Scraper", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0, 15))

        tb.Label(right_frame, text="JustDial URL:", font=("Segoe UI", 10, "bold")).pack(anchor=W, pady=(0, 5))
        self.single_url_var = tb.StringVar()
        url_entry = tb.Entry(right_frame, textvariable=self.single_url_var, font=("Segoe UI", 10))
        url_entry.pack(fill=X, pady=(0, 10))

        self.single_scrape_btn = tb.Button(right_frame, text="🚀 Scrape This URL", command=self.start_single_url_scrape, bootstyle="success")
        self.single_scrape_btn.pack(fill=X)

    def setup_dashboard_tab(self):
        self.dashboard_tab = tb.Frame(self.notebook, padding=20)
        self.notebook.add(self.dashboard_tab, text="📊 Dashboard")

        # Header
        header_frame = tb.Frame(self.dashboard_tab)
        header_frame.pack(fill=X, pady=(0, 15))
        tb.Label(header_frame, text="Scraped Businesses", font=("Segoe UI", 18, "bold")).pack(side=LEFT)
        self.refresh_btn = tb.Button(header_frame, text="🔄 Refresh", command=self.refresh_dashboard, bootstyle="primary")
        self.refresh_btn.pack(side=RIGHT)

        # Stats
        self.stats_frame = tb.Frame(self.dashboard_tab)
        self.stats_frame.pack(fill=X, pady=(0, 15))
        self.total_label = tb.Label(self.stats_frame, text="0", font=("Segoe UI", 36, "bold"), foreground="#3498db")
        self.total_label.grid(row=0, column=0, padx=(0, 50))
        tb.Label(self.stats_frame, text="Total Businesses", font=("Segoe UI", 12)).grid(row=1, column=0, padx=(0, 50), sticky=N)

        self.images_label = tb.Label(self.stats_frame, text="0", font=("Segoe UI", 36, "bold"), foreground="#27ae60")
        self.images_label.grid(row=0, column=1, padx=(0, 50))
        tb.Label(self.stats_frame, text="Total Images", font=("Segoe UI", 12)).grid(row=1, column=1, padx=(0, 50), sticky=N)

        self.menu_label = tb.Label(self.stats_frame, text="0", font=("Segoe UI", 36, "bold"), foreground="#f39c12")
        self.menu_label.grid(row=0, column=2)
        tb.Label(self.stats_frame, text="Total Menu Items", font=("Segoe UI", 12)).grid(row=1, column=2, sticky=N)

        # Search bar
        search_frame = tb.Frame(self.dashboard_tab)
        search_frame.pack(fill=X, pady=(0, 10))
        tb.Label(search_frame, text="🔍 Search:", font=("Segoe UI", 10, "bold")).pack(side=LEFT, padx=(0, 10))
        self.search_var = tb.StringVar()
        self.search_entry = tb.Entry(search_frame, textvariable=self.search_var, font=("Segoe UI", 10))
        self.search_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
        self.search_var.trace_add("write", self.on_search_change)

        # Treeview
        tree_frame = tb.Frame(self.dashboard_tab)
        tree_frame.pack(fill=BOTH, expand=True)
        tb.Label(tree_frame, text="📋 Business List", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0, 10))

        columns = ("#", "Name", "Category", "Phone", "WhatsApp", "Address")
        self.business_tree = tb.Treeview(tree_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.business_tree.heading(col, text=col)
            if col == "#":
                self.business_tree.column(col, width=50)
            elif col == "Name":
                self.business_tree.column(col, width=220)
            elif col == "Address":
                self.business_tree.column(col, width=280)
            else:
                self.business_tree.column(col, width=140)

        scrollbar = tb.Scrollbar(tree_frame, orient=VERTICAL, command=self.business_tree.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.business_tree.configure(yscrollcommand=scrollbar.set)
        self.business_tree.pack(side=LEFT, fill=BOTH, expand=True)

        self.business_tree.bind("<<TreeviewSelect>>", self.on_business_select)
        self.business_tree.bind("<Double-1>", self.on_tree_double_click)

        # Action buttons below
        btn_frame = tb.Frame(self.dashboard_tab)
        btn_frame.pack(fill=X, pady=(10, 0))
        self.details_btn = tb.Button(btn_frame, text="📋 View Details", command=self.show_business_details, bootstyle="primary", state=DISABLED)
        self.details_btn.pack(side=LEFT, padx=(0, 10))
        
        self.delete_btn = tb.Button(btn_frame, text="🗑️ Delete Business", command=self.delete_selected_business, bootstyle="danger", state=DISABLED)
        self.delete_btn.pack(side=LEFT)

    def setup_log(self):
        log_frame = tb.Frame(self.main_container)
        log_frame.pack(fill=X, expand=False)
        tb.Label(log_frame, text="📜 Activity Log", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=WORD, height=7, font=("Consolas", 9), bg="#1a1a2e", fg="#00ff00", insertbackground="#00ff00")
        self.log_text.pack(fill=X, expand=True)

    def on_state_change(self, event):
        selected = self.state_var.get()
        self.district_combo["values"] = INDIAN_STATES.get(selected, [])
        self.district_combo.current(0)

    def on_main_cat_change(self, event):
        selected = self.main_cat_var.get()
        subcats = self.categories.get(selected, {}).get("subcategories", [])
        self.subcat_combo["values"] = subcats
        if subcats:
            self.subcat_combo.current(0)

    def refresh_categories(self):
        self.log("🔄 Refreshing categories...")
        self.categories = fetch_categories_from_justdial()
        self.main_cat_combo["values"] = list(self.categories.keys())
        self.log("✅ Categories refreshed!")

    def on_search_change(self, *args):
        self.filter_business_list()

    def filter_business_list(self):
        search_text = self.search_var.get().lower()
        
        # Clear tree
        for item in self.business_tree.get_children():
            self.business_tree.delete(item)

        # Filter and insert matching businesses
        for idx, bus in enumerate(self.all_businesses):
            name = bus.get("name", "").lower()
            category = bus.get("category", "").lower()
            phone = bus.get("phone", "")
            address = bus.get("address", "").lower()
            
            if (search_text in name or 
                search_text in category or 
                search_text in phone or 
                search_text in address):
                self.business_tree.insert("", END, values=(
                    idx + 1,
                    bus.get("name", "").strip()[:45],
                    bus.get("category", "").strip()[:30],
                    bus.get("phone", ""),
                    bus.get("whatsapp", ""),
                    bus.get("address", "").strip()[:40]
                ))

    def refresh_dashboard(self):
        """Refresh dashboard in a background thread to keep UI responsive"""
        # Disable the refresh button while loading
        self.refresh_btn.config(state=tk.DISABLED)
        self.log("🔄 Refreshing dashboard...")
        
        def do_refresh():
            try:
                # Fetch data from API
                stats_resp = requests.get("http://localhost:8000/api/v1/stats", timeout=5)
                rest_resp = requests.get("http://localhost:8000/api/v1/restaurants", timeout=5)
                
                # Update UI on the main thread
                self.after(0, self._update_dashboard_ui, stats_resp, rest_resp)
            except Exception as e:
                self.after(0, lambda: self.log(f"⚠️  Failed to refresh: {str(e)}"))
                self.after(0, lambda: self.refresh_btn.config(state=tk.NORMAL))
        
        # Start refresh in a background thread
        threading.Thread(target=do_refresh, daemon=True).start()

    def _update_dashboard_ui(self, stats_resp, rest_resp):
        """Update the dashboard UI (must be called from main thread)"""
        try:
            # Clear tree and cache
            self.photo_images = []
            self.all_businesses = []
            for item in self.business_tree.get_children():
                self.business_tree.delete(item)
            
            # Update stats
            if stats_resp and stats_resp.ok:
                stats = stats_resp.json()
                self.total_label.config(text=str(stats.get("total_restaurants", 0)))
                self.images_label.config(text=str(stats.get("total_images", 0)))
                self.menu_label.config(text=str(stats.get("total_menu_items", 0)))
            
            # Disable treeview redraw while inserting to make it *way* faster
            self.business_tree.configure(show="tree")  # Hide temporarily to avoid redraw
            self.update_idletasks()
            
            # Insert new data
            if rest_resp and rest_resp.ok:
                businesses = rest_resp.json()
                for idx, bus in enumerate(businesses):
                    self.all_businesses.append(bus)
                    self.business_tree.insert("", END, values=(
                        idx + 1,
                        bus.get("name", "").strip()[:45],
                        bus.get("category", "").strip()[:30],
                        bus.get("phone", ""),
                        bus.get("whatsapp", ""),
                        bus.get("address", "").strip()[:40]
                    ))
            
            # Re-enable treeview
            self.business_tree.configure(show="headings tree")
            
            self.log("✅ Dashboard refreshed!")
        except Exception as e:
            self.log(f"⚠️  Failed to update UI: {str(e)}")
        finally:
            self.refresh_btn.config(state=tk.NORMAL)

    def delete_selected_business(self):
        selection = self.business_tree.selection()
        if not selection:
            messagebox.showwarning("Select Business", "Please select a business from the list to delete!")
            return
        
        # Get selected item
        item_values = self.business_tree.item(selection[0], "values")
        serial_num = int(item_values[0]) - 1
        
        if serial_num < 0 or serial_num >= len(self.all_businesses):
            messagebox.showerror("Error", "Invalid selection. Please refresh the dashboard and try again!")
            return
        
        bus = self.all_businesses[serial_num]
        bus_id = bus.get("id")
        num_images = len(bus.get("images", []))
        
        self.log(f"🔍 Debug: Selected business ID = {bus_id}")
        
        # Super clear confirmation dialog
        msg = f"""⚠️ PLEASE READ CAREFULLY ⚠️
        
You are about to delete:
{'-'*40}
Business Name: {bus.get('name', 'N/A')}
Category: {bus.get('category', 'N/A')}
Phone: {bus.get('phone', 'N/A')}
Saved Images: {num_images}
{'-'*40}

What would you like to do?"""
        
        # Create a custom dialog with clear buttons
        root = self
        
        class DeleteConfirmDialog:
            def __init__(self, parent, business_name, num_imgs):
                self.result = None
                self.top = tk.Toplevel(parent)
                self.top.title("⚠️ Confirm Deletion")
                self.top.geometry("550x400")
                self.top.resizable(False, False)
                
                # Make dialog modal
                self.top.transient(parent)
                self.top.grab_set()
                
                # Center dialog
                self.top.update_idletasks()
                width = self.top.winfo_width()
                height = self.top.winfo_height()
                x = (self.top.winfo_screenwidth() // 2) - (width // 2)
                y = (self.top.winfo_screenheight() // 2) - (height // 2)
                self.top.geometry(f'{width}x{height}+{x}+{y}')
                
                # Header
                header = tk.Label(self.top, text="DELETE BUSINESS", font=("Segoe UI", 16, "bold"), fg="#e74c3c")
                header.pack(pady=15)
                
                # Info
                info_frame = tk.Frame(self.top)
                info_frame.pack(pady=10, padx=20)
                
                tk.Label(info_frame, text=f"Business Name:", font=("Segoe UI", 10, "bold"), anchor="w").grid(row=0, column=0, sticky="w", pady=2)
                tk.Label(info_frame, text=business_name, font=("Segoe UI", 10), anchor="w").grid(row=0, column=1, sticky="w", pady=2)
                
                tk.Label(info_frame, text=f"Number of Images:", font=("Segoe UI", 10, "bold"), anchor="w").grid(row=1, column=0, sticky="w", pady=2)
                tk.Label(info_frame, text=str(num_imgs), font=("Segoe UI", 10), anchor="w").grid(row=1, column=1, sticky="w", pady=2)
                
                # Buttons
                btn_frame = tk.Frame(self.top)
                btn_frame.pack(pady=25)
                
                # Yes button
                yes_btn = tk.Button(btn_frame, text=f"✅ Delete Business + {num_imgs} Image(s)", 
                                   font=("Segoe UI", 11, "bold"), bg="#e74c3c", fg="white",
                                   command=lambda: self.set_result(True), height=2, width=25)
                yes_btn.grid(row=0, column=0, padx=10)
                
                # No button
                no_btn = tk.Button(btn_frame, text=f"🗄️ Delete Business Only (Keep Images)", 
                                  font=("Segoe UI", 11), bg="#3498db", fg="white",
                                  command=lambda: self.set_result(False), height=2, width=25)
                no_btn.grid(row=0, column=1, padx=10)
                
                # Cancel button
                cancel_btn = tk.Button(btn_frame, text="❌ Cancel", 
                                      font=("Segoe UI", 11), bg="#95a5a6", fg="white",
                                      command=lambda: self.set_result(None), height=2, width=25)
                cancel_btn.grid(row=0, column=2, padx=10)
                
                self.top.wait_window()
                
            def set_result(self, res):
                self.result = res
                self.top.destroy()
        
        dialog = DeleteConfirmDialog(root, bus.get("name", "Unknown"), num_images)
        result = dialog.result
        
        if result is None:
            self.log("🗑️ Delete cancelled by user.")
            return
        
        delete_images = result
        
        # Show feedback before deleting
        if delete_images:
            self.log(f"🗑️ Deleting business '{bus.get('name')}' and {num_images} image(s)...")
        else:
            self.log(f"🗑️ Deleting business '{bus.get('name')}' (keeping images)...")
        
        # Call delete API
        try:
            self.log(f"🔍 Debug: Sending delete request for ID {bus_id}")
            resp = requests.delete(f"http://localhost:8000/api/v1/restaurant/{bus_id}", 
                                  params={"delete_images": delete_images},
                                  timeout=10)
            if resp.ok:
                self.log(f"✅ Successfully deleted business: {bus.get('name')}")
                self.refresh_dashboard()
                messagebox.showinfo("Success", f"Successfully deleted business:\n{bus.get('name')}")
            else:
                self.log(f"❌ Failed to delete business: {resp.text}")
                messagebox.showerror("Delete Failed", f"Failed to delete business:\n{resp.text}")
        except requests.exceptions.Timeout:
            self.log("❌ Error: Request timed out. Please try again.")
            messagebox.showerror("Timeout Error", "The request timed out. Please check your connection and try again.")
        except Exception as e:
            self.log(f"❌ Error deleting business: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            messagebox.showerror("Error", f"An error occurred while deleting:\n{str(e)}")

    def on_business_select(self, event):
        if self.business_tree.selection():
            self.details_btn.config(state=NORMAL)
            self.delete_btn.config(state=NORMAL)
        else:
            self.details_btn.config(state=DISABLED)
            self.delete_btn.config(state=DISABLED)

    def on_tree_double_click(self, event):
        self.show_business_details()

    def show_business_details(self):
        selection = self.business_tree.selection()
        if not selection:
            return
        
        # Get selected item's serial number and find in all_businesses
        item_values = self.business_tree.item(selection[0], "values")
        serial_num = int(item_values[0]) - 1
        
        if 0 <= serial_num < len(self.all_businesses):
            bus = self.all_businesses[serial_num]
        else:
            return
            
        bus_name = bus.get("name", "Business Details")
        short_name = (bus_name[:20] + "...") if len(bus_name) > 20 else bus_name

        # Check if tab already exists
        for tab_id in self.notebook.tabs():
            if self.notebook.tab(tab_id, "text") == short_name:
                self.notebook.select(tab_id)
                return

        # Create new tab
        details_tab = tb.Frame(self.notebook, padding=20)
        self.notebook.add(details_tab, text=short_name)
        self.notebook.select(details_tab)

        # Header with close button
        header_frame = tb.Frame(details_tab)
        header_frame.pack(fill=X, pady=(0, 15))
        tb.Label(header_frame, text=bus_name, font=("Segoe UI", 20, "bold")).pack(side=LEFT)
        tb.Button(header_frame, text="✕ Close", command=lambda: self.notebook.forget(details_tab), bootstyle="danger").pack(side=RIGHT)

        # Info grid
        info_frame = tb.Frame(details_tab)
        info_frame.pack(fill=X, pady=(0, 15))

        row = 0
        for key, label_text in [
            ("category", "Category:"), ("phone", "Phone:"), ("whatsapp", "WhatsApp:"),
            ("address", "Address:"), ("opening_hours", "Hours:"), ("jd_url", "JustDial URL:")
        ]:
            value = bus.get(key, "")
            if value:
                tb.Label(info_frame, text=label_text, font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky=W, pady=5)
                tb.Label(info_frame, text=value, font=("Segoe UI", 10)).grid(row=row, column=1, sticky=W, pady=5)
                row += 1

        # Menu Items
        menu_items = bus.get("menu_items", [])
        if menu_items:
            menu_frame = tb.Frame(details_tab)
            menu_frame.pack(fill=BOTH, expand=True, pady=(0, 15))
            tb.Label(menu_frame, text="🍽️ Menu Items", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0, 10))

            menu_tree = tb.Treeview(menu_frame, columns=("Item", "Price", "Veg?"), show="headings", height=10)
            menu_tree.heading("Item", text="Item")
            menu_tree.heading("Price", text="Price")
            menu_tree.heading("Veg?", text="Veg?")
            menu_tree.column("Item", width=350)
            menu_tree.column("Price", width=100)
            menu_tree.column("Veg?", width=80)
            menu_tree.pack(fill=BOTH, expand=True)

            for item in menu_items:
                veg_text = "✅ Yes" if item.get("is_veg", True) else "❌ No"
                price_text = "₹" + str(item.get("price", "0"))
                menu_tree.insert("", END, values=(
                    item.get("name", ""),
                    price_text,
                    veg_text
                ))

        # Images
        img_frame = tb.Frame(details_tab)
        img_frame.pack(fill=BOTH, expand=True)
        tb.Label(img_frame, text="🖼️ Scraped Images", font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0, 10))

        if bus.get("images"):
            img_canvas = tb.Canvas(img_frame)
            img_scroll = tb.Scrollbar(img_frame, orient=HORIZONTAL, command=img_canvas.xview)
            img_inner_frame = tb.Frame(img_canvas)
            img_inner_frame.bind("<Configure>", lambda e: img_canvas.configure(scrollregion=img_canvas.bbox("all")))
            img_canvas.create_window((0, 0), window=img_inner_frame, anchor="nw")
            img_canvas.configure(xscrollcommand=img_scroll.set)
            img_scroll.pack(side=BOTTOM, fill=X)
            img_canvas.pack(side=TOP, fill=BOTH, expand=True)

            for i, img_path in enumerate(bus["images"]):
                # Use absolute path directly from DB
                full_path = img_path
                if os.path.exists(full_path):
                    try:
                        img = Image.open(full_path)
                        img.verify()  # Verify it's a valid image
                        img.close()
                        img = Image.open(full_path)  # Reopen after verify
                        img.thumbnail((200, 200))
                        photo = ImageTk.PhotoImage(img)
                        self.photo_images.append(photo)
                        lbl = tb.Label(img_inner_frame, image=photo)
                        lbl.grid(row=0, column=i, padx=5, pady=5)
                    except Exception as e:
                        # Just skip invalid images without logging to avoid clutter
                        pass
                else:
                    # Skip missing images
                    pass
        else:
            tb.Label(img_frame, text="No scraped images for this business", font=("Segoe UI", 10), foreground="#aaa").pack(anchor=W)

    def start_scrape(self):
        if self.is_scraping:
            return
        self.is_scraping = True
        set_stop_flag(False)
        self.status_label.config(text="Status: Scraping...", foreground="#f39c12")
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.single_scrape_btn.config(state=DISABLED)

        district = self.district_var.get()
        main_cat = self.main_cat_var.get()
        subcat = self.subcat_var.get()
        max_rest = self.max_var.get()

        thread = threading.Thread(target=self.run_scrape, args=(district, main_cat, subcat, max_rest))
        thread.daemon = True
        thread.start()

    def stop_scrape(self):
        set_stop_flag(True)
        self.log("🛑 Stop command sent!")

    def run_scrape(self, district, main_cat, subcat, max_rest):
        try:
            self.log(f"🚀 Starting scrape: {district} | {main_cat}")
            original_stdout = sys.stdout
            class LogRedirector:
                def __init__(self, app): self.app = app
                def write(self, text):
                    if text.strip():
                        self.app.log(text.rstrip())
                def flush(self): pass
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
            self.status_label.config(text="Status: Ready", foreground="#2ecc71")
            self.start_btn.config(state=NORMAL)
            self.stop_btn.config(state=DISABLED)
            self.single_scrape_btn.config(state=NORMAL)

    def start_single_url_scrape(self):
        if self.is_scraping:
            return
        url = self.single_url_var.get().strip()
        if not url or "justdial.com" not in url:
            messagebox.showwarning("Warning", "Enter a valid JustDial URL!")
            return

        self.is_scraping = True
        set_stop_flag(False)
        self.start_btn.config(state=DISABLED)
        self.single_scrape_btn.config(state=DISABLED)

        thread = threading.Thread(target=self.run_single_scrape, args=(url,))
        thread.daemon = True
        thread.start()

    def run_single_scrape(self, url):
        try:
            self.log(f"🚀 Scraping single URL...")
            original_stdout = sys.stdout
            class LogRedirector:
                def __init__(self, app): self.app = app
                def write(self, text):
                    if text.strip():
                        self.app.log(text.rstrip())
                def flush(self): pass
            sys.stdout = LogRedirector(self)
            success = scrape_single_url(url)
            sys.stdout = original_stdout
            if success:
                self.log("✅ Done!")
                self.refresh_dashboard()
            else:
                self.log("❌ Failed!")
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
        finally:
            self.is_scraping = False
            set_stop_flag(False)
            self.start_btn.config(state=NORMAL)
            self.single_scrape_btn.config(state=NORMAL)

    def log(self, message):
        if not hasattr(self, "log_text"):
            return
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            self.log_text.insert(END, f"[{ts}] {message}\n")
            self.log_text.see(END)
        except Exception:
            pass

    def on_close(self):
        if self.fastapi_process:
            try:
                self.fastapi_process.terminate()
                self.log("✅ FastAPI server stopped!")
            except Exception:
                pass
        self.destroy()

def main():
    app = ModernScraperApp()
    app.mainloop()

if __name__ == "__main__":
    main()
