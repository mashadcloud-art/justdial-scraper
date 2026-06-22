import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Activity,
  AppWindow,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Clock,
  Database,
  Download,
  ExternalLink,
  FileSpreadsheet,
  Gauge,
  Image as ImageIcon,
  LayoutDashboard,
  Link2,
  MapPin,
  Maximize2,
  MessageCircle,
  Minimize2,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Play,
  RefreshCw,
  Search,
  Settings,
  Square,
  Star,
  Sun,
  Trash2,
  UtensilsCrossed,
  X,
  Zap,
} from "lucide-react";
import { useTheme } from "@/hooks/use-theme";
import { Button } from "@/components/ui/button";
import ListingsManager from "@/components/ListingsManager";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [{ title: "JustDial Pro Scraper v3.0 — Premium extraction suite" }],
  }),
  component: Dashboard,
});

/* ─── Types ───────────────────────────────────────────────── */
type MenuItem = { item: string; price: string; veg: boolean };

type Business = {
  id: string;
  name: string;
  category: string;
  location: string;
  address: string;
  phone: string;
  whatsapp: string;
  hours: string;
  justdialUrl: string;
  rating: number;
  reviews: number;
  latitude?: string;
  longitude?: string;
  images: { path: string; category: string }[];
  menuItems: MenuItem[];
  amenities: { category: string; value: string }[];
};

type Tab = "scraper" | "dashboard" | "listings" | { type: "detail"; business: Business };
type LogEntry = { time: string; ok: boolean; msg: string };
type Status = "Ready" | "Scraping..." | "Complete" | "Stopped";

/* ─── Static data ──────────────────────────────────────────── */
const STATES = [
  "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh",
  "Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka",
  "Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram",
  "Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana",
  "Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
  "Delhi","Jammu & Kashmir","Ladakh","Chandigarh","Puducherry",
];

const CITIES: Record<string, string[]> = {
  "Andhra Pradesh": ["Visakhapatnam","Vijayawada","Guntur","Nellore","Kurnool","Tirupati","Rajahmundry","Kakinada","Anantapur","Eluru","Ongole","Srikakulam","Vizianagaram","Chittoor","Kadapa"],
  "Arunachal Pradesh": ["Itanagar","Naharlagun","Pasighat","Tezpur"],
  "Assam": ["Guwahati","Silchar","Dibrugarh","Jorhat","Nagaon","Tezpur","Tinsukia","Bongaigaon","Dhubri","Goalpara","Karimganj"],
  "Bihar": ["Patna","Gaya","Bhagalpur","Muzaffarpur","Darbhanga","Purnia","Arrah","Bihar Sharif","Begusarai","Katihar","Saharsa","Sasaram","Hajipur","Siwan","Chapra"],
  "Chhattisgarh": ["Raipur","Bhilai","Bilaspur","Korba","Durg","Rajnandgaon","Jagdalpur","Ambikapur","Raigarh","Dhamtari"],
  "Goa": ["Panaji","Margao","Vasco da Gama","Mapusa","Ponda","Bicholim","Calangute","Candolim"],
  "Gujarat": ["Ahmedabad","Surat","Vadodara","Rajkot","Bhavnagar","Jamnagar","Gandhinagar","Junagadh","Anand","Navsari","Morbi","Nadiad","Surendranagar","Bharuch","Porbandar","Mehsana","Patan","Amreli"],
  "Haryana": ["Faridabad","Gurgaon","Panipat","Ambala","Hisar","Karnal","Rohtak","Sonipat","Yamunanagar","Panchkula","Bhiwani","Bahadurgarh","Sirsa","Rewari","Kaithal","Kurukshetra"],
  "Himachal Pradesh": ["Shimla","Mandi","Dharamshala","Solan","Kangra","Kullu","Manali","Baddi","Palampur","Hamirpur","Una","Bilaspur"],
  "Jharkhand": ["Ranchi","Jamshedpur","Dhanbad","Bokaro","Hazaribagh","Deoghar","Phusro","Chirkunda","Giridih","Ramgarh"],
  "Karnataka": ["Bengaluru","Mysuru","Mangaluru","Hubli","Belagavi","Kalaburagi","Davangere","Shivamogga","Tumkur","Bidar","Raichur","Vijayapura","Bagalkot","Hassan","Udupi","Dharwad","Chitradurga","Ballari","Mandya","Chikkamagaluru","Kodagu"],
  "Kerala": ["Thiruvananthapuram","Kollam","Pathanamthitta","Alappuzha","Kottayam","Idukki","Ernakulam","Thrissur","Palakkad","Malappuram","Kozhikode","Wayanad","Kannur","Kasaragod","Kochi","Thiruvalla","Thrippunithura","Kalamassery","Perumbavoor","Muvattupuzha","Angamaly","Chalakudy","Irinjalakuda","Guruvayur","Kunnamkulam","Ponnani","Tirur","Manjeri","Kalpetta","Thalassery","Vatakara","Payyannur"],
  "Madhya Pradesh": ["Bhopal","Indore","Gwalior","Jabalpur","Ujjain","Sagar","Dewas","Satna","Ratlam","Rewa","Murwara","Singrauli","Burhanpur","Khandwa","Bhind","Chhindwara","Damoh","Mandsaur","Khargone","Neemuch","Vidisha"],
  "Maharashtra": ["Mumbai","Pune","Nagpur","Thane","Nashik","Aurangabad","Solapur","Navi Mumbai","Pimpri-Chinchwad","Amravati","Kolhapur","Sangli","Malegaon","Jalgaon","Akola","Latur","Dhule","Ahmednagar","Ichalkaranji","Chandrapur","Parbhani","Jalna","Bhusawal","Nanded","Ratnagiri","Satara","Baramati","Vasai-Virar","Mira-Bhayandar"],
  "Manipur": ["Imphal","Thoubal","Bishnupur","Churachandpur","Senapati"],
  "Meghalaya": ["Shillong","Tura","Jowai","Nongstoin"],
  "Mizoram": ["Aizawl","Lunglei","Champhai","Serchhip"],
  "Nagaland": ["Kohima","Dimapur","Mokokchung","Tuensang","Wokha"],
  "Odisha": ["Bhubaneswar","Cuttack","Rourkela","Berhampur","Sambalpur","Puri","Balasore","Baripada","Bhadrak","Jharsuguda","Angul","Dhenkanal","Kendujhar","Paradip"],
  "Punjab": ["Ludhiana","Amritsar","Jalandhar","Patiala","Bathinda","Mohali","Hoshiarpur","Gurdaspur","Pathankot","Moga","Firozpur","Muktsar","Sangrur","Barnala","Fatehgarh Sahib","Kapurthala","Nawanshahr","Ropar","Faridkot"],
  "Rajasthan": ["Jaipur","Jodhpur","Udaipur","Kota","Ajmer","Bikaner","Alwar","Bharatpur","Sikar","Pali","Sri Ganganagar","Tonk","Barmer","Jhunjhunu","Chittorgarh","Bhilwara","Nagaur","Hanumangarh","Banswara","Sawai Madhopur"],
  "Sikkim": ["Gangtok","Namchi","Mangan","Gyalshing"],
  "Tamil Nadu": ["Chennai","Coimbatore","Madurai","Tiruchirappalli","Salem","Tirunelveli","Erode","Vellore","Tiruppur","Dindigul","Thanjavur","Ranipet","Sivakasi","Karur","Udhagamandalam","Hosur","Nagercoil","Kanchipuram","Kumbakonam","Tiruvannamalai","Pollachi","Rajapalayam","Gudiyatham","Pudukkottai","Nagapattinam","Viluppuram","Cuddalore"],
  "Telangana": ["Hyderabad","Warangal","Nizamabad","Karimnagar","Khammam","Ramagundam","Mahbubnagar","Nalgonda","Adilabad","Suryapet","Miryalaguda","Siddipet","Jagtial","Mancherial"],
  "Tripura": ["Agartala","Dharmanagar","Udaipur","Kailasahar","Belonia"],
  "Uttar Pradesh": ["Lucknow","Kanpur","Agra","Varanasi","Meerut","Prayagraj","Ghaziabad","Noida","Bareilly","Aligarh","Moradabad","Saharanpur","Gorakhpur","Firozabad","Jhansi","Muzaffarnagar","Mathura","Rampur","Shahjahanpur","Farrukhabad","Hapur","Etawah","Mainpuri","Hardoi","Sitapur","Lakhimpur","Unnao","Rae Bareli","Banda","Chitrakoot","Fatehpur","Pratapgarh","Kaushambi","Deoria","Azamgarh","Ballia","Jaunpur","Sultanpur","Faizabad","Ambedkar Nagar","Bahraich","Shravasti","Gonda","Basti","Siddharthnagar","Maharajganj","Kushinagar","Gorakhpur"],
  "Uttarakhand": ["Dehradun","Haridwar","Roorkee","Haldwani","Rudrapur","Kashipur","Rishikesh","Kotdwar","Ramnagar","Mussoorie","Nainital","Almora","Pithoragarh"],
  "West Bengal": ["Kolkata","Howrah","Durgapur","Asansol","Siliguri","Bardhaman","Malda","Baharampur","Habra","Kharagpur","Shantipur","Dankuni","Dhulian","Ranaghat","Haldia","Raiganj","Krishnanagar","Nabadwip","Medinipur","Balurghat","Bankura","Chakdaha","Darjeeling","Alipurduar","Cooch Behar","Jalpaiguri","Purulia"],
  "Delhi": ["New Delhi","North Delhi","South Delhi","East Delhi","West Delhi","Central Delhi","North East Delhi","North West Delhi","South East Delhi","South West Delhi","Dwarka","Rohini","Saket","Lajpat Nagar","Karol Bagh","Connaught Place","Janakpuri","Pitampura","Shahdara","Preet Vihar"],
  "Jammu & Kashmir": ["Srinagar","Jammu","Anantnag","Sopore","Baramulla","Kathua","Udhampur","Rajouri","Punch","Doda"],
  "Ladakh": ["Leh","Kargil"],
  "Chandigarh": ["Chandigarh","Mohali","Panchkula"],
  "Puducherry": ["Puducherry","Karaikal","Mahe","Yanam"],
};
const CATEGORIES = [
  "Home Services","Restaurants","Hospitals","Hotels","Education",
  "Real Estate","Automobile","Beauty & Spa","Doctors","Travel",
  "Home Decor",
];
const SUBCATEGORIES: Record<string, string[]> = {
  "Home Services": ["Plumbers","Electricians","Carpenters","Painters","Cleaners"],
  Restaurants: ["Fast Food","Fine Dining","Cafes","Bakeries","Chinese"],
  Hospitals: ["Multi-Specialty","Dental","Eye Care","Orthopedic","Pediatric"],
  Hotels: ["Budget","3 Star","4 Star","5 Star","Resorts"],
  Education: ["Schools","Colleges","Coaching","Play Schools","Music Classes"],
  "Real Estate": ["Agents","Builders","PG / Hostels","Rentals"],
  Automobile: ["Car Dealers","Bike Dealers","Service Centres","Spare Parts"],
  "Beauty & Spa": ["Salons","Spas","Nail Art","Tattoo"],
  Doctors: ["General Physician","Cardiologist","Dermatologist","Gynaecologist"],
  Travel: ["Travel Agents","Cab Services","Tour Operators","Airlines"],
  "Home Decor": ["Furnitures","Furnishing","Lamps-Lighting","Kitchen-Dining","Interior-Designers"],
};

const MOCK_MENUS: MenuItem[][] = [
  [
    { item: "Prawns Biryani", price: "₹450", veg: false },
    { item: "Boneless Chicken Biryani", price: "₹360", veg: false },
    { item: "Tonic Water (250ml)", price: "₹50", veg: true },
    { item: "Kesar Pista Milkshake", price: "₹140", veg: true },
    { item: "Moong Dal Halwa", price: "₹140", veg: true },
    { item: "Chocolate Brownie", price: "₹140", veg: true },
    { item: "Strawberry Milkshake", price: "₹140", veg: true },
    { item: "Gulab Jamun (12 nos)", price: "₹130", veg: true },
  ],
  [
    { item: "Masala Dosa", price: "₹120", veg: true },
    { item: "Idli Sambar", price: "₹80", veg: true },
    { item: "Butter Chicken", price: "₹320", veg: false },
    { item: "Paneer Tikka", price: "₹280", veg: true },
    { item: "Veg Fried Rice", price: "₹180", veg: true },
  ],
  [
    { item: "Club Sandwich", price: "₹220", veg: false },
    { item: "Caesar Salad", price: "₹180", veg: true },
    { item: "Cappuccino", price: "₹120", veg: true },
    { item: "Cold Coffee", price: "₹150", veg: true },
  ],
];

const SAMPLE_IMAGES = [
  "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800",
  "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=800",
  "https://images.unsplash.com/photo-1486325212027-8081e485255e?w=800",
  "https://images.unsplash.com/photo-1497366216548-37526070297c?w=800",
  "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=800",
  "https://images.unsplash.com/photo-1582407947304-fd86f028f716?w=800",
  "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800",
  "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=800",
];

function makeBusiness(index: number, sub: string, city: string, state: string): Business {
  const names = [
    `${sub} Hub`, `Royal ${sub}`, `${city} ${sub} Centre`,
    `Premium ${sub}`, `Elite ${sub}`, `Star ${sub}`,
    `${sub} Palace`, `Modern ${sub}`, `Classic ${sub}`, `Urban ${sub}`,
  ];
  const streets = [
    "MG Road", "Nehru Street", "Gandhi Nagar", "Park Avenue",
    "Civil Lines", "Station Road", "Market Street", "Lake View Road",
  ];
  const name = names[index % names.length];
  const street = streets[index % streets.length];
  const phone = `+91 ${Math.floor(Math.random() * 9000000000 + 1000000000)}`;
  return {
    id: `${Date.now()}-${index}`,
    name,
    category: sub,
    location: `${city}, ${state}`,
    address: `${index + 1}/${index + 10}, ${street}, Near City Mall, ${city} - ${600000 + index * 11}, ${state}`,
    phone,
    whatsapp: phone.replace("+91 ", ""),
    hours: "Mon - Sun :- 9:00 am - 10:00 pm",
    justdialUrl: `https://www.justdial.com/${city.replace(/\s/g, "-")}/${name.replace(/\s/g, "-")}/0484PX484-X484-${Date.now()}`,
    rating: parseFloat((3.5 + Math.random() * 1.5).toFixed(1)),
    reviews: Math.floor(Math.random() * 2000) + 10,
    images: [
      { path: SAMPLE_IMAGES[index % SAMPLE_IMAGES.length], category: "Food" },
      { path: SAMPLE_IMAGES[(index + 1) % SAMPLE_IMAGES.length], category: "Ambience" },
      { path: SAMPLE_IMAGES[(index + 2) % SAMPLE_IMAGES.length], category: "By Owner" },
    ],
    menuItems: MOCK_MENUS[index % MOCK_MENUS.length],
    amenities: [
      { category: "Serves", value: "Coffee" },
      { category: "Serves", value: "Biryani" },
      { category: "Serves", value: "Fast Food" },
      { category: "Serves", value: "Street Food" },
      { category: "Services", value: "Home Delivery" }
    ],
  };
}

function ts() {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

/* ─── Dashboard ────────────────────────────────────────────── */
function Dashboard() {
  const { theme, toggle } = useTheme();
  const [activeTab, setActiveTab] = useState<Tab>("scraper");
  const [detailTabs, setDetailTabs] = useState<Business[]>([]);
  const [maximized, setMaximized] = useState(false);
  // sidebar: collapsed by default (compact mode), expanded when maximized
  const sidebarCollapsed = !maximized;
  const [logModalOpen, setLogModalOpen] = useState(false);

  // No auto-resize logic — layout is driven purely by maximize toggle

  // Scraper form
  const [state, setState] = useState("Kerala");
  const [city, setCity] = useState("Ernakulam");
  const [category, setCategory] = useState("Restaurants");
  const [subcategory, setSubcategory] = useState("Fast Food");
  const [maxEntries, setMaxEntries] = useState(10);
  const [fastMode, setFastMode] = useState(false);
  const [singleUrl, setSingleUrl] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [listingCount, setListingCount] = useState<string | null>(null);
  const [fetchingCount, setFetchingCount] = useState(false);
  const [engine, setEngine] = useState("api");
  const [emulatorJson, setEmulatorJson] = useState("");
  const [ingestingJson, setIngestingJson] = useState(false);
  const [adbLocation, setAdbLocation] = useState("");
  const [importUrl, setImportUrl] = useState("");
  const [importingUrl, setImportingUrl] = useState(false);
  const [categoryTree, setCategoryTree] = useState<any[]>([]);

  // Proxy state variables
  const [proxyRunning, setProxyRunning] = useState(false);
  const [phoneProxy, setPhoneProxy] = useState("Unknown");
  const [proxyToggling, setProxyToggling] = useState(false);
  
  // Compiled JSONs browser states
  const [compiledJsons, setCompiledJsons] = useState<any[]>([]);
  const [loadingJsons, setLoadingJsons] = useState(false);
  const [viewingJsonContent, setViewingJsonContent] = useState<string | null>(null);
  const [viewingJsonFilename, setViewingJsonFilename] = useState<string | null>(null);
  const [isJsonModalOpen, setIsJsonModalOpen] = useState(false);

  // Poll proxy status
  useEffect(() => {
    async function checkProxyStatus() {
      try {
        const res = await fetch(`${LOCAL_API}/adb/proxy/status`);
        if (res.ok) {
          const data = await res.json();
          setProxyRunning(data.running);
          setPhoneProxy(data.phone_proxy);
        }
      } catch { /* ignore */ }
    }
    checkProxyStatus();
    const interval = setInterval(checkProxyStatus, 4000);
    return () => clearInterval(interval);
  }, []);

  // Fetch compiled JSONs list
  async function fetchCompiledJsons() {
    setLoadingJsons(true);
    try {
      const res = await fetch(`${API}/compiled-jsons`);
      if (res.ok) {
        const data = await res.json();
        setCompiledJsons(data);
      }
    } catch { /* ignore */ }
    finally { setLoadingJsons(false); }
  }

  useEffect(() => {
    fetchCompiledJsons();
  }, []);

  // Toggle Proxy Routing
  async function toggleProxyRouting() {
    setProxyToggling(true);
    const action = proxyRunning ? "stop" : "start";
    try {
      const res = await fetch(`${LOCAL_API}/adb/proxy/${action}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        if (data.status === "warning") {
          toast.warning(data.message);
        } else {
          toast.success(data.message);
        }
        setProxyRunning(action === "start");
        // Refetch immediately
        const statusRes = await fetch(`${LOCAL_API}/adb/proxy/status`);
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          setPhoneProxy(statusData.phone_proxy);
        }
      } else {
        toast.error(`Failed to ${action} proxy routing`);
      }
    } catch (e: any) {
      toast.error(`Connection error: ${e.message}`);
    } finally {
      setProxyToggling(false);
    }
  }

  // View compiled JSON file
  async function viewJsonFile(filename: string) {
    try {
      const res = await fetch(`${API}/compiled-jsons/${filename}`);
      if (res.ok) {
        const data = await res.json();
        setViewingJsonContent(JSON.stringify(data, null, 2));
        setViewingJsonFilename(filename);
        setIsJsonModalOpen(true);
      } else {
        toast.error("Failed to load JSON file");
      }
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  // Delete compiled JSON file
  async function deleteJsonFile(filename: string) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
    try {
      const res = await fetch(`${API}/compiled-jsons/${filename}`, { method: "DELETE" });
      if (res.ok) {
        toast.success(`Deleted ${filename}`);
        await fetchCompiledJsons();
      } else {
        toast.error("Failed to delete file");
      }
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  // Category listing counts from "Check Listings"
  type CategoryCount = { category: string; count: string };
  const [categoryCountsModal, setCategoryCountsModal] = useState(false);
  const [categoryCounts, setCategoryCounts] = useState<CategoryCount[]>([]);
  const [checkingListings, setCheckingListings] = useState(false);

  // Scrape
  const [status, setStatus] = useState<Status>("Ready");
  const [progress, setProgress] = useState(0);
  const [running, setRunning] = useState(false);
  const [totalScraped, setTotalScraped] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const API = "/api/v1";
  const LOCAL_API = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" || window.location.hostname === "::1" ? "/api/v1" : "http://localhost:8000/api/v1";

  // Results
  const [rows, setRows] = useState<Business[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [lightbox, setLightbox] = useState<{ images: string[]; index: number; name: string } | null>(null);
  const [sortKey, setSortKey] = useState<keyof Business>("id");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Log
  const [log, setLog] = useState<LogEntry[]>([
    { time: "00:00:00", ok: true, msg: "FastAPI server started successfully!" },
    { time: "00:00:01", ok: true, msg: "JustDial Pro Scraper v3.0 ready." },
  ]);
  const logRef = useRef<HTMLDivElement>(null);

  // Stats
  const [statsTotal, setStatsTotal] = useState(0);
  const [statsImages, setStatsImages] = useState(0);

  // Load real data from API on mount
  useEffect(() => {
    fetchStats();
    fetchRestaurants();
  }, []);

  async function fetchStats() {
    try {
      const res = await fetch(`${API}/stats`);
      if (res.ok) {
        const data = await res.json();
        setStatsTotal(data.total_restaurants ?? 0);
        setStatsImages(data.total_images ?? 0);
      }
    } catch { /* backend not ready yet */ }
  }

  function getImageUrl(p: string) {
    if (!p) return "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800";
    if (p.startsWith("http")) return p;
    
    const norm = p.replace(/\\/g, "/");
    if (norm.includes("uploaded_images/")) {
      const filename = norm.split("uploaded_images/").pop();
      return `/uploaded_images/${filename}`;
    }
    if (norm.includes("scraped_images/")) {
      const filename = norm.split("scraped_images/").pop();
      return `/scraped_images/${filename}`;
    }
    return `/${norm}`;
  }

  async function fetchRestaurants() {
    try {
      const res = await fetch(`${API}/restaurants?page=1&limit=1000`);
      if (res.ok) {
        const responseData = await res.json();
        const data: any[] = responseData.data || [];
        const mapped: Business[] = data.map((r) => ({
          id: String(r.id),
          name: r.name,
          category: r.category || "General",
          location: r.address?.split(",").slice(-2).join(",").trim() || "—",
          address: r.address || "—",
          phone: r.phone || "—",
          whatsapp: r.whatsapp || r.phone || "—",
          hours: r.opening_hours || "—",
          justdialUrl: r.jd_url || "",
          latitude: r.latitude,
          longitude: r.longitude,
          rating: 4.0 + Math.random() * 1,
          reviews: Math.floor(Math.random() * 500) + 10,
          images: r.images?.length
            ? r.images.map((img: any) => ({
                path: getImageUrl(img.path),
                category: img.category || "general"
              }))
            : [{ path: "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800", category: "general" }],
          menuItems: (r.menu_items || []).map((m: any) => ({
            item: m.name,
            price: m.price ? `₹${m.price}` : "—",
            veg: m.is_veg ?? true,
          })),
          amenities: (r.amenities || []).map((a: any) => ({
            category: a.category || "General",
            value: a.value || ""
          })),
          latitude: r.latitude || "",
          longitude: r.longitude || "",
        }));
        setRows(mapped);
        setTotalScraped(mapped.length);
        addLog(true, `Loaded ${mapped.length} businesses from database.`);
      }
    } catch { addLog(false, "Could not connect to backend API."); }
  }

  useEffect(() => {
    const cities = CITIES[state] ?? [];
    setCity(cities[0] ?? "");
    setListingCount(null);
    setCategoryCounts([]);
  }, [state]);
  useEffect(() => {
    // Don't auto-select subcategory — let user choose
    setListingCount(null);
  }, [category]);

  // Fetch listing count from backend when city/subcategory changes
  useEffect(() => {
    if (!city || !subcategory) return;
    setListingCount(null);
    setFetchingCount(true);
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `${API}/listing-count?city=${encodeURIComponent(city)}&category=${encodeURIComponent(subcategory)}`
        );
        if (res.ok) {
          const data = await res.json();
          setListingCount(data.count ? `${data.count}+ listings found` : null);
        }
      } catch { /* ignore */ }
      finally { setFetchingCount(false); }
    }, 800); // debounce
    return () => clearTimeout(timer);
  }, [city, subcategory]);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log]);

  function addLog(ok: boolean, msg: string) {
    setLog((l) => [...l, { time: ts(), ok, msg }]);
  }

  async function checkListings() {
    if (!city) return;
    setCheckingListings(true);
    setCategoryCounts([]);
    addLog(true, `Checking listings for ${city}...`);
    const results: CategoryCount[] = [];
    for (const cat of CATEGORIES) {
      try {
        const res = await fetch(
          `${API}/listing-count?city=${encodeURIComponent(city)}&category=${encodeURIComponent(cat)}`
        );
        if (res.ok) {
          const data = await res.json();
          results.push({ category: cat, count: data.count ? `${data.count}+` : "—" });
        } else {
          results.push({ category: cat, count: "—" });
        }
      } catch {
        results.push({ category: cat, count: "—" });
      }
    }
    setCategoryCounts(results);
    setCategoryCountsModal(true);
    setCheckingListings(false);
    addLog(true, `Listings check complete for ${city}.`);
  }

  function openDetail(b: Business) {
    if (!detailTabs.find((t) => t.id === b.id)) {
      setDetailTabs((dt) => [...dt, b]);
    }
    setActiveTab({ type: "detail", business: b });
  }

  function closeDetail(id: string) {
    setDetailTabs((dt) => dt.filter((t) => t.id !== id));
    setActiveTab("dashboard");
  }

  async function ingestEmulatorJson() {
    if (!emulatorJson.trim()) {
      toast.error("Please paste the JSON first");
      return;
    }
    try {
      // Basic validation
      const parsed = JSON.parse(emulatorJson);
      if (!parsed.results || !parsed.results.data) {
        toast.error("Invalid JSON format. Make sure it contains results.data");
        return;
      }
    } catch (e) {
      toast.error("Invalid JSON string. Could not parse.");
      return;
    }

    setIngestingJson(true);
    addLog(true, "Ingesting Mobile Emulator JSON...");
    try {
      const res = await fetch(`${API}/ingest-emulator-json`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          json_data: emulatorJson,
          state,
          district: city,
          category,
          subcategory
        })
      });

      if (res.ok) {
        const data = await res.json();
        toast.success(`Successfully extracted ${data.extracted_count} businesses!`);
        addLog(true, `Emulator Ingestion complete: extracted ${data.extracted_count} records.`);
        setEmulatorJson(""); // Clear input
        await fetchRestaurants();
        await fetchStats();
      } else {
        toast.error("Failed to ingest JSON");
        addLog(false, "Failed to ingest JSON from backend");
      }
    } catch (e) {
      toast.error("Network error submitting JSON");
      addLog(false, "Network error submitting JSON");
    } finally {
      setIngestingJson(false);
    }
  }

  async function startScraping() {
    if (running) return;
    setRunning(true);
    setStatus("Scraping...");
    setProgress(15);
    addLog(true, `Starting scrape: ${category} › ${subcategory} in ${city}, ${state}`);
    addLog(true, `Max entries: ${maxEntries}`);
    
    try {
      const url = `${API}/scrape?state=${encodeURIComponent(state)}&district=${encodeURIComponent(city)}&main_cat=${encodeURIComponent(category)}&subcat=${encodeURIComponent(subcategory === "All" ? "" : subcategory)}&max_limit=${maxEntries}&fast_mode=${fastMode}&engine=${engine}`;
      const res = await fetch(url, { method: "POST" });
      if (res.ok) {
        addLog(true, "Scraping task successfully submitted to backend. Running...");
        setProgress(35);
        
        // Start polling the scraper status from the backend
        let localProgress = 35;
        let lastIdx = 0;
        const intervalId = setInterval(async () => {
          try {
            const statusRes = await fetch(`${API}/scrape/status?last_idx=${lastIdx}`);
            if (statusRes.ok) {
              const statusData = await statusRes.json();
              
              if (statusData.logs && statusData.logs.length > 0) {
                setLog((l) => [...l, ...statusData.logs]);
                lastIdx = statusData.next_idx;
              }
              
              if (statusData.running === false) {
                // Done!
                clearInterval(intervalId);
                setProgress(100);
                setRunning(false);
                setStatus("Complete");
                toast.success("Scrape complete", { description: "Businesses scraped successfully" });
                await fetchRestaurants();
                await fetchStats();
                setActiveTab("dashboard");
              } else {
                // Still running, increment progress indicator up to 90%
                localProgress = Math.min(localProgress + 5, 90);
                setProgress(localProgress);
                await fetchStats(); // Fetch stats dynamically during scraping
              }
            }
          } catch (err) {
            // Ignore polling errors
          }
        }, 1500);
        
        timerRef.current = intervalId;
      } else {
        const err = await res.text();
        addLog(false, `Scraper failed to start: ${err}`);
        setRunning(false);
        setStatus("Stopped");
      }
    } catch (e: any) {
      addLog(false, `Connection error starting scraper: ${e.message}`);
      setRunning(false);
      setStatus("Stopped");
    }
  }

  async function ingestEmulatorJson() {
    if (!emulatorJson.trim()) {
      toast.error("Please paste the JSON output from HTTP Toolkit first.");
      return;
    }
    
    setIngestingJson(true);
    addLog(true, `Starting Emulator JSON Ingestion...`);
    
    try {
      // Validate JSON first
      let parsed;
      try {
        parsed = JSON.parse(emulatorJson);
      } catch (e) {
        toast.error("Invalid JSON format");
        addLog(false, "Failed to parse JSON string");
        setIngestingJson(false);
        return;
      }
      
      const res = await fetch(`${API}/ingest-emulator-json?district=${encodeURIComponent(city)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: emulatorJson
      });
      
      if (res.ok) {
        const data = await res.json();
        addLog(true, `Successfully ingested ${data.count} restaurants from emulator JSON.`);
        toast.success(`Ingested ${data.count} restaurants!`);
        setEmulatorJson("");
        await fetchRestaurants();
        await fetchStats();
      } else {
        addLog(false, `Ingestion failed.`);
        toast.error("Upload failed");
      }
    } catch (e) {
      addLog(false, `Ingestion error: ${e}`);
    } finally {
      setIngestingJson(false);
    }
  }

  async function ingestSavedFolder() {
    setIngestingJson(true);
    addLog(true, `Starting Bulk Folder Ingestion from Desktop (JustDial_JSONs)...`);
    
    try {
      const res = await fetch(`${API}/ingest-saved-folder?district=${encodeURIComponent(city)}`, {
        method: "POST"
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success") {
          addLog(true, data.message);
          toast.success(data.message);
          await fetchRestaurants();
          await fetchStats();
        } else {
          addLog(false, `Folder ingestion failed: ${data.message}`);
          toast.error(data.message);
        }
      } else {
        addLog(false, `Folder ingestion HTTP failed.`);
        toast.error("Bulk upload failed");
      }
    } catch (e: any) {
      addLog(false, `Folder ingestion error: ${e.message}`);
      toast.error("Upload error");
    } finally {
      setIngestingJson(false);
    }
  }

  async function triggerAdbSearch() {
    if (running) return;
    if (!adbLocation.trim()) {
      toast.error("Please enter a Target Location (PIN or Town) first!");
      return;
    }
    setRunning(true);
    setStatus("Scraping...");
    setProgress(10);
    addLog(true, `Starting Emulator Search: Location '${adbLocation}', Category '${category}', Scrolls ${maxEntries}`);
    
    try {
      const url = `${LOCAL_API}/adb/search?location=${encodeURIComponent(adbLocation.trim())}&category=${encodeURIComponent(category)}&scrolls=${maxEntries}`;
      const res = await fetch(url, { method: "POST" });
      if (res.ok) {
        addLog(true, "ADB search task successfully submitted to emulator. Running...");
        setProgress(25);
        
        let localProgress = 25;
        let lastIdx = 0;
        const intervalId = setInterval(async () => {
          try {
            const statusRes = await fetch(`${API}/scrape/status?last_idx=${lastIdx}`);
            if (statusRes.ok) {
              const statusData = await statusRes.json();
              
              if (statusData.logs && statusData.logs.length > 0) {
                setLog((l) => [...l, ...statusData.logs]);
                lastIdx = statusData.next_idx;
              }
              
              if (statusData.running === false) {
                // We also check /adb/status to be absolutely sure the emulator process is finished
                const adbStatusRes = await fetch(`${LOCAL_API}/adb/status`);
                const adbStatusData = await adbStatusRes.json();
                if (adbStatusData.running === false) {
                  clearInterval(intervalId);
                  setProgress(100);
                  setRunning(false);
                  setStatus("Complete");
                  toast.success("ADB Search Complete", { description: "Emulator automation completed!" });
                  await fetchRestaurants();
                  await fetchStats();
                }
              } else {
                localProgress = Math.min(localProgress + 5, 95);
                setProgress(localProgress);
              }
            }
          } catch (err) {
            // Ignore polling errors
          }
        }, 1500);
        
        timerRef.current = intervalId;
      } else {
        const err = await res.text();
        addLog(false, `ADB Search failed to start: ${err}`);
        setRunning(false);
        setStatus("Stopped");
      }
    } catch (e: any) {
      addLog(false, `Connection error starting ADB Search: ${e.message}`);
      setRunning(false);
      setStatus("Stopped");
    }
  }

  function stopScraping() {
    if (timerRef.current) clearInterval(timerRef.current);
    setRunning(false);
    setStatus("Stopped");
    addLog(false, "Scraping stopped by user.");
    toast.error("Scraping stopped");
  }

  async function refreshCategories() {
    addLog(true, "Refreshing category list from JustDial...");
    toast.info("Refreshing categories...");
    try {
      await fetch(`${API}/categories/fetch-from-justdial?city=${city}`);
      addLog(true, "Categories refreshed successfully.");
      toast.success("Categories refreshed");
    } catch {
      addLog(false, "Failed to refresh categories.");
      toast.error("Failed to refresh categories");
    }
  }

  async function handleImportUrl() {
    if (!importUrl.trim()) {
      toast.error("Please enter a JustDial category URL first");
      return;
    }
    setImportingUrl(true);
    addLog(true, `Importing categories from JustDial URL: ${importUrl}`);
    try {
      const res = await fetch(`${API}/categories/import-from-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: importUrl })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success" && data.tree.length > 0) {
          const newCategoryName = data.main_category;
          
          // Flatten tree to get a list of all category names for fallback
          const subNames: string[] = [];
          data.tree.forEach((node: any) => {
            subNames.push(node.name);
            if (node.children) {
              node.children.forEach((c: any) => {
                subNames.push(c.name);
              });
            }
          });
          
          toast.success(`Successfully imported ${subNames.length} categories!`);
          addLog(true, `Successfully imported ${data.tree.length} subcategories and nested child categories under "${newCategoryName}".`);
          
          if (!CATEGORIES.includes(newCategoryName)) {
            CATEGORIES.push(newCategoryName);
          }
          SUBCATEGORIES[newCategoryName] = subNames;
          
          setCategoryTree(data.tree);
          setCategory(newCategoryName);
          setSubcategory(subNames[0] || "All");
          setImportUrl("");
        } else {
          toast.error("No categories found in this URL");
          addLog(false, "No categories found in this URL");
        }
      } else {
        toast.error("Failed to parse the URL");
        addLog(false, "Failed to parse the URL");
      }
    } catch (e: any) {
      toast.error(`Import failed: ${e.message}`);
      addLog(false, `Import failed: ${e.message}`);
    } finally {
      setImportingUrl(false);
    }
  }

  async function scrapeUrl() {
    if (!singleUrl.trim()) { toast.error("Enter a JustDial URL first"); addLog(false, "Single URL scrape failed: no URL provided."); return; }
    addLog(true, `Scraping URL: ${singleUrl}`);
    toast.info("Scraping URL...");
    setRunning(true);
    setStatus("Scraping...");
    setProgress(15);
    
    try {
      const res = await fetch(`${API}/scrape/single?url=${encodeURIComponent(singleUrl)}&fast_mode=${fastMode}&engine=${engine}`, { method: "POST" });
      if (res.ok) {
        addLog(true, "Single URL scrape successfully submitted to backend. Running...");
        setProgress(35);
        
        let localProgress = 35;
        let lastIdx = 0;
        const intervalId = setInterval(async () => {
          try {
            const statusRes = await fetch(`${API}/scrape/status?last_idx=${lastIdx}`);
            if (statusRes.ok) {
              const statusData = await statusRes.json();
              
              if (statusData.logs && statusData.logs.length > 0) {
                setLog((l) => [...l, ...statusData.logs]);
                lastIdx = statusData.next_idx;
              }
              
              if (statusData.running === false) {
                clearInterval(intervalId);
                setProgress(100);
                setRunning(false);
                setStatus("Complete");
                toast.success("Single URL scrape complete", { description: "Business scraped successfully" });
                await fetchRestaurants();
                await fetchStats();
                setActiveTab("dashboard");
              } else {
                localProgress = Math.min(localProgress + 10, 90);
                setProgress(localProgress);
                await fetchStats();
              }
            }
          } catch (err) {
            // Ignore polling errors
          }
        }, 1500);
        
        timerRef.current = intervalId;
      } else {
        const err = await res.text();
        addLog(false, `Single URL scrape failed to start: ${err}`);
        setRunning(false);
        setStatus("Stopped");
      }
    } catch (e: any) {
      addLog(false, `Connection error starting single URL scraper: ${e.message}`);
      setRunning(false);
      setStatus("Stopped");
    }
  }

  const filtered = [...rows]
    .filter((r) => { 
      const q = searchQuery.toLowerCase(); 
      return !q || 
        r.name.toLowerCase().includes(q) || 
        r.category.toLowerCase().includes(q) || 
        r.location.toLowerCase().includes(q) ||
        r.address.toLowerCase().includes(q); 
    })
    .sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (sortKey === "id") {
        return sortDir === "asc" ? Number(av) - Number(bv) : Number(bv) - Number(av);
      }
      const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
      return sortDir === "asc" ? cmp : -cmp;
    });

  const toggleRow = (id: string) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleAll = () => setSelected((s) => s.size === filtered.length ? new Set() : new Set(filtered.map((r) => r.id)));
  const sort = (k: keyof Business) => { if (sortKey === k) setSortDir((d) => d === "asc" ? "desc" : "asc"); else { setSortKey(k); setSortDir("asc"); } };
  const exportData = (kind: "csv" | "xlsx") => { const target = selected.size > 0 ? rows.filter((r) => selected.has(r.id)) : filtered; toast.success(`Exported ${target.length} rows as ${kind.toUpperCase()}`); };

  const confirmBulkDelete = async () => {
    const ids = Array.from(selected);
    for (const id of ids) {
      try { await fetch(`${API}/restaurant/${id}`, { method: "DELETE" }); } catch { /* ignore */ }
    }
    setRows((rs) => rs.filter((r) => !selected.has(r.id)));
    toast.success(`Deleted ${selected.size} records`);
    setSelected(new Set());
    setConfirmOpen(false);
    await fetchStats();
  };

  const cities = CITIES[state] ?? [];
  const subs = SUBCATEGORIES[category] ?? [];

  const getSubcategoryOptions = () => {
    if (categoryTree && categoryTree.length > 0) {
      const formatted: any[] = ["All"];
      categoryTree.forEach((sub1) => {
        const hasChildren = sub1.children && sub1.children.length > 0;
        formatted.push({
          label: sub1.name,
          value: sub1.name,
          indent: 0,
          hasChildren: hasChildren
        });
        if (hasChildren) {
          sub1.children.forEach((sub2: any) => {
            formatted.push({
              label: sub2.name,
              value: sub2.name,
              indent: 1,
              parent: sub1.name
            });
          });
        }
      });
      return formatted;
    }
    return ["All", ...(subs.length ? subs : ["—"])];
  };

  const statusColor = { "Ready": "text-emerald-400", "Scraping...": "text-amber-400", "Complete": "text-emerald-400", "Stopped": "text-red-400" }[status];
  const isDetailTab = typeof activeTab === "object" && activeTab.type === "detail";
  const activeTabId = isDetailTab ? (activeTab as { type: "detail"; business: Business }).business.id : null;

  return (
    <div className={cn(
      "relative flex bg-background text-foreground overflow-hidden transition-all duration-300",
      maximized
        ? "w-screen h-screen"                                           // full browser window
        : "w-[1024px] h-[600px] mx-auto mt-4 rounded-xl ring-1 ring-border shadow-2xl" // default app size
    )}>

      {/* ── Sidebar ── */}
      <aside className={cn(
        "shrink-0 border-r border-border flex flex-col transition-all duration-200 overflow-hidden",
        sidebarCollapsed
          ? "w-14 bg-[#1a1a2e]"          // dark slim rail
          : "w-56 bg-sidebar"             // full light/dark sidebar
      )}>

        {/* Logo row */}
        <div className={cn(
          "flex items-center gap-2.5 py-4 border-b transition-all",
          sidebarCollapsed
            ? "justify-center px-0 border-white/10"
            : "px-4 border-border"
        )}>
          <div
            className="size-8 rounded-lg flex items-center justify-center text-white font-bold shrink-0"
            style={{ background: "var(--gradient-brand)" }}
          >
            J
          </div>
          {!sidebarCollapsed && (
            <div className="flex flex-col min-w-0">
              <span className="font-semibold tracking-tight text-sm leading-none truncate">JustDial Pro</span>
              <span className="text-[10px] text-brand font-mono mt-0.5">v3.0 PREMIUM</span>
            </div>
          )}
        </div>

        {/* Nav items */}
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          <NavItem icon={<Zap className="size-4" />}           label="Scraper"         active={activeTab === "scraper"}   onClick={() => setActiveTab("scraper")}   collapsed={sidebarCollapsed} dark={sidebarCollapsed} />
          <NavItem icon={<LayoutDashboard className="size-4" />} label="Dashboard"     active={activeTab === "dashboard"} onClick={() => setActiveTab("dashboard")} collapsed={sidebarCollapsed} dark={sidebarCollapsed} />
          <NavItem icon={<Database className="size-4" />}      label="Proxy Manager"                                                                                collapsed={sidebarCollapsed} dark={sidebarCollapsed} />
          <NavItem icon={<Download className="size-4" />}      label="Export History"                                                                               collapsed={sidebarCollapsed} dark={sidebarCollapsed} />

          {/* Open record tabs — only in expanded mode */}
          {detailTabs.length > 0 && !sidebarCollapsed && (
            <div className="pt-2 mt-2 border-t border-sidebar-border space-y-0.5">
              <p className="px-2 text-[9px] uppercase tracking-widest text-muted-foreground font-bold mb-1">Open Records</p>
              {detailTabs.map((b) => (
                <div
                  key={b.id}
                  className={cn(
                    "w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-medium transition-all group",
                    activeTabId === b.id
                      ? "bg-card text-foreground ring-1 ring-border shadow-sm"
                      : "text-muted-foreground hover:text-foreground hover:bg-sidebar-accent"
                  )}
                >
                  <button className="flex-1 text-left truncate" onClick={() => setActiveTab({ type: "detail", business: b })}>
                    <span className={cn("mr-1", activeTabId === b.id && "text-brand")}>📋</span>
                    {b.name.length > 16 ? b.name.slice(0, 16) + "…" : b.name}
                  </button>
                  <button onClick={() => closeDetail(b.id)} className="opacity-0 group-hover:opacity-100 hover:text-destructive transition-all shrink-0">
                    <X className="size-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </nav>

        {/* Credits — expanded only */}
        {!sidebarCollapsed && (
          <div className="px-3 pb-3 border-t border-sidebar-border pt-3">
            <div className="rounded-xl bg-card ring-1 ring-border p-2.5">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Credits</span>
                <span className="text-[9px] font-mono text-brand">42%</span>
              </div>
              <div className="text-xs font-semibold mb-1.5">12,402 / 30,000</div>
              <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{ width: "42%", background: "var(--gradient-brand)" }} />
              </div>
            </div>
          </div>
        )}

        {/* Collapsed — avatar + settings at bottom */}
        {sidebarCollapsed && (
          <div className="flex flex-col items-center gap-3 pb-4 pt-2 border-t border-white/10">
            <button className="size-8 rounded-full bg-brand/20 flex items-center justify-center text-brand hover:bg-brand/30 transition-colors" title="Profile">
              <span className="text-xs font-bold">A</span>
            </button>
            <button className="size-7 flex items-center justify-center text-white/40 hover:text-white/80 transition-colors" title="Settings">
              <Settings className="size-4" />
            </button>
          </div>
        )}

        {/* Collapse / expand toggle */}
        <button
          onClick={() => setMaximized((v) => !v)}
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "flex items-center justify-center h-9 border-t transition-colors",
            sidebarCollapsed
              ? "border-white/10 text-white/40 hover:text-white hover:bg-white/5"
              : "border-border text-muted-foreground hover:text-foreground hover:bg-sidebar-accent"
          )}
        >
          {sidebarCollapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
        </button>
      </aside>

      {/* ── Main ── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Header */}
        <header className="h-12 shrink-0 border-b border-border flex items-center justify-between px-4 bg-background/60 backdrop-blur">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xs text-muted-foreground hidden sm:block">Home /</span>
            <span className="text-sm font-semibold capitalize truncate">
              {activeTab === "scraper" ? "Scraper" : activeTab === "dashboard" ? "Dashboard" : activeTab === "listings" ? "Listings Queue" : (activeTab as { type: "detail"; business: Business }).business.name}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden lg:flex items-center gap-2 px-3 h-8 rounded-lg ring-1 ring-border bg-card w-48">
              <Search className="size-3.5 text-muted-foreground shrink-0" />
              <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Search..." className="bg-transparent text-xs flex-1 outline-none placeholder:text-muted-foreground" />
            </div>
            <button onClick={toggle} className="size-8 rounded-lg ring-1 ring-border bg-card flex items-center justify-center hover:bg-accent transition-colors" aria-label="Toggle theme">
              {theme === "dark" ? <Sun className="size-3.5" /> : <Moon className="size-3.5" />}
            </button>
            <button className="size-8 rounded-lg ring-1 ring-border bg-card flex items-center justify-center hover:bg-accent transition-colors">
              <Settings className="size-3.5" />
            </button>
            {/* Maximize / Restore button */}
            <button
              onClick={() => setMaximized((v) => !v)}
              title={maximized ? "Restore default size" : "Maximize"}
              className="size-8 rounded-lg ring-1 ring-border bg-card flex items-center justify-center hover:bg-accent transition-colors"
            >
              {maximized ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
            </button>
            {/* Pop-out — open as standalone mini window */}
            <button
              onClick={() => {
                const w = 1024, h = 600;
                const left = Math.round(window.screen.width / 2 - w / 2);
                const top = Math.round(window.screen.height / 2 - h / 2);
                window.open(
                  window.location.href,
                  "JustDialPro",
                  `width=${w},height=${h},left=${left},top=${top},resizable=yes,scrollbars=no,toolbar=no,menubar=no,location=no,status=no`
                );
              }}
              title="Pop out as mini window"
              className="size-8 rounded-lg ring-1 ring-border bg-card flex items-center justify-center hover:bg-accent transition-colors"
            >
              <AppWindow className="size-3.5" />
            </button>
            <div className="h-8 px-2.5 rounded-lg text-white text-xs font-medium flex items-center shadow-brand" style={{ background: "var(--gradient-brand)" }}>
              Alex R.
            </div>
          </div>
        </header>

        {/* Content */}
        <div className={cn("flex-1 min-h-0", maximized ? "overflow-y-auto" : "overflow-hidden flex flex-col")}>
          <div className={cn("animate-entrance w-full", maximized ? "p-5 space-y-5 max-w-[1400px] mx-auto" : "p-2 flex flex-col gap-2 flex-1 min-h-0")}>

            {/* ── STAT CARDS ── */}
            {maximized ? (
              /* Maximized: 4 wide cards in a single row */
              <div className="grid grid-cols-4 gap-4">
                <StatCardLg label="Total Businesses" value={statsTotal.toLocaleString()} trend="+12% this hour" icon={<Database className="size-4" />} live />
                <StatCardLg label="Scraped Today"    value={totalScraped.toLocaleString()} trend={running ? "In progress..." : "Ready"} icon={<Zap className="size-4" />} />
                <StatCardLg label="Images Collected" value={(statsImages/1000).toFixed(1)+"k"} trend="Stored locally" icon={<ImageIcon className="size-4" />} />
                <StatCardLg label="Success Rate"     value="99.4%" trend="142 req/min" icon={<Gauge className="size-4" />} />
              </div>
            ) : (
              /* Default: 4 cards in a single horizontal row */
              <div className="grid grid-cols-4 gap-2">
                <StatCard label="Total Businesses" value={statsTotal.toLocaleString()} trend="+12% this hour" icon={<Database className="size-3.5" />} live />
                <StatCard label="Scraped Today"    value={totalScraped.toLocaleString()} trend={running ? "In progress..." : "Ready"} icon={<Zap className="size-3.5" />} />
                <StatCard label="Images"           value={(statsImages/1000).toFixed(1)+"k"} trend="Stored locally" icon={<ImageIcon className="size-3.5" />} />
                <StatCard label="Success Rate"     value="99.4%" trend="142 req/min" icon={<Gauge className="size-3.5" />} />
              </div>
            )}

            {/* ── SCRAPER TAB ── */}
            {activeTab === "scraper" && (
              maximized ? (
                /* ══ MAXIMIZED SCRAPER LAYOUT ══ */
                <>
                  <div className="grid grid-cols-2 gap-5">
                    {/* Location & Category — spacious */}
                    <section className="p-6 rounded-2xl ring-1 ring-border bg-card shadow-elegant space-y-4">
                      <div className="flex items-center gap-2">
                        <MapPin className="size-4 text-brand" />
                        <h3 className="text-base font-semibold">Location & Category</h3>
                        {fetchingCount && <span className="text-xs text-muted-foreground animate-pulse ml-2">checking...</span>}
                        {listingCount && !fetchingCount && (
                          <span className="ml-auto text-xs font-mono px-2 py-0.5 rounded-full bg-brand/10 text-brand font-semibold">{listingCount}</span>
                        )}
                      </div>
                      {/* Search */}
                      <div className="flex items-center gap-2 h-10 px-3 rounded-lg ring-1 ring-border bg-background focus-within:ring-brand transition-all">
                        <Search className="size-3.5 text-muted-foreground shrink-0" />
                        <input
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          placeholder="Search businesses..."
                          className="bg-transparent text-sm flex-1 outline-none placeholder:text-muted-foreground"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <FormField label="State / UT"><StyledSelectLg value={state} onChange={setState} options={STATES} /></FormField>
                        <FormField label="District / City"><StyledSelectLg value={city} onChange={setCity} options={cities.length ? cities : ["—"]} /></FormField>
                        <FormField label="Main Category">
                          <StyledSelectLg
                            value={category}
                            onChange={setCategory}
                            options={CATEGORIES}
                            counts={Object.fromEntries(categoryCounts.map((c) => [c.category, c.count]))}
                          />
                        </FormField>
                        <FormField label="Subcategory">
                          <StyledSelectLg
                            value={subcategory}
                            onChange={setSubcategory}
                            options={getSubcategoryOptions()}
                          />
                        </FormField>
                        <FormField label="Scraper Engine">
                          <StyledSelectLg
                            value={
                              engine === "api" ? "⚡ API (Chrome)" : 
                              engine === "api_edge" ? "⚡ API (Edge)" : 
                              engine === "selenium" ? "Chrome Driver" : 
                              engine === "edge" ? "Edge Driver" : 
                              engine === "playwright" ? "Playwright (Chrome)" : 
                              engine === "playwright_edge" ? "Playwright (Edge)" : 
                              engine === "emulator" ? "📱 Mobile Emulator" : 
                              "Playwright (Chrome)"
                            }
                            onChange={(v) => {
                              if (v.includes("API (Chrome)")) setEngine("api");
                              else if (v.includes("API (Edge)")) setEngine("api_edge");
                              else if (v.includes("Chrome Driver")) setEngine("selenium");
                              else if (v.includes("Edge Driver")) setEngine("edge");
                              else if (v.includes("Playwright (Chrome)")) setEngine("playwright");
                              else if (v.includes("Playwright (Edge)")) setEngine("playwright_edge");
                              else if (v.includes("Mobile")) setEngine("emulator");
                            }}
                            options={["⚡ API (Chrome)", "⚡ API (Edge)", "Chrome Driver", "Edge Driver", "Playwright (Chrome)", "Playwright (Edge)", "📱 Mobile Emulator"]}
                          />
                        </FormField>
                        <FormField label="Max Entries">
                          <input
                            type="number" min={1} max={500} value={maxEntries}
                            onChange={(e) => setMaxEntries(Math.max(1, Number(e.target.value)))}
                            className="w-full h-10 rounded-lg px-3 text-sm bg-background ring-1 ring-border outline-none focus:ring-brand transition-all"
                          />
                        </FormField>
                      </div>
                      


                      {/* Fast Mode Checkbox */}
                      <div className="flex items-center gap-2 mt-2">
                        <Checkbox id="fastModeLg" checked={fastMode} onCheckedChange={(checked) => setFastMode(!!checked)} />
                        <label htmlFor="fastModeLg" className="text-xs font-semibold text-muted-foreground cursor-pointer select-none">
                          ⚡ Fast Mode (URLs only — No image downloads)
                        </label>
                      </div>

                      {/* Category URL Importer */}
                      <div className="border-t pt-4 mt-4 space-y-2">
                        <label className="text-xs font-semibold block">
                          📥 Import Categories from JustDial URL
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={importUrl}
                            onChange={(e) => setImportUrl(e.target.value)}
                            placeholder="https://www.justdial.com/Kutch/Home-Decor/fil-297"
                            className="flex-1 h-9 rounded-lg px-3 text-xs bg-background ring-1 ring-border outline-none focus:ring-brand transition-all"
                          />
                          <Button 
                            onClick={handleImportUrl} 
                            disabled={importingUrl}
                            size="sm"
                            className="h-9 px-3 bg-brand text-white font-medium rounded-lg text-xs shrink-0"
                          >
                            {importingUrl ? "Importing..." : "Import"}
                          </Button>
                        </div>
                        <p className="text-[10px] text-muted-foreground">
                          Paste a JustDial category page URL (e.g., Home Decor) to automatically parse and load all its subcategories into the selectors.
                        </p>
                      </div>
                    </section>

                    {/* Right column */}
                    <div className="flex flex-col gap-5">
                      {/* Controls */}
                      <section className="p-6 rounded-2xl ring-1 ring-border bg-card shadow-elegant space-y-4">
                        <div className="flex items-center justify-between">
                          <h3 className="text-base font-semibold">Controls</h3>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Status:</span>
                            <span className={cn("text-sm font-semibold", statusColor)}>{status}</span>
                            {running && <span className="size-2 rounded-full bg-amber-400 animate-pulse" />}
                          </div>
                        </div>
                        {running && (
                          <div className="space-y-1.5">
                            <div className="flex justify-between text-xs font-medium">
                              <span className="text-muted-foreground">Processing records...</span>
                              <span className="text-brand font-mono">{Math.round(progress)}%</span>
                            </div>
                            <Progress value={progress} className="h-1.5" />
                          </div>
                        )}
                        <div className="grid grid-cols-3 gap-3">
                          <Button onClick={startScraping} disabled={running} className="h-10 text-white font-medium shadow-brand" style={{ background: running ? undefined : "var(--gradient-brand)" }}>
                            <Play className="size-4 mr-2" />{running ? "Running..." : "Start Scraping"}
                          </Button>
                          <Button onClick={stopScraping} disabled={!running} variant="outline" className="h-10">
                            <Square className="size-4 mr-2" />Stop Scraping
                          </Button>
                          <Button onClick={refreshCategories} variant="secondary" className="h-10">
                            <RefreshCw className="size-4 mr-2" />Refresh
                          </Button>
                        </div>
                      </section>

                      {/* Emulator Control Center */}
                      {engine === "emulator" && (
                        <section className="p-6 rounded-2xl ring-1 ring-border bg-card shadow-elegant space-y-6">
                          <div className="flex items-center gap-2 border-b pb-3">
                            <Database className="size-5 text-brand" />
                            <h3 className="text-base font-semibold">📱 Emulator Control Center</h3>
                          </div>
                          
                          {/* Sub-section 1: Remote Control Search */}
                          <div className="space-y-3">
                            <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                              <Play className="size-3.5 text-brand" />
                              1. Remote Emulator Search
                            </h4>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                              Automatically launch JustDial, type the location PIN/Town, and scroll the listing page to capture payloads.
                            </p>
                            <div className="grid grid-cols-2 gap-3 items-end">
                              <div className="col-span-2">
                                <FormField label="Target Location (PIN or Town)">
                                  <input 
                                    type="text" 
                                    value={adbLocation} 
                                    onChange={(e) => setAdbLocation(e.target.value)} 
                                    className="w-full h-10 rounded-lg px-3 text-sm bg-background ring-1 ring-border outline-none focus:ring-brand" 
                                    placeholder="e.g. 671315" 
                                  />
                                </FormField>
                              </div>
                              <Button 
                                onClick={triggerAdbSearch} 
                                disabled={running}
                                className="w-full h-10 text-white font-medium shadow-brand text-xs" 
                                style={{ background: running ? undefined : "var(--gradient-brand)" }}
                              >
                                {running ? "Running..." : "Manual PIN Search"}
                              </Button>
                                <Button 
                                  onClick={async () => {
                                    if (!state || !city || !category) {
                                      toast.error("Please select State, District, and Category first!");
                                      return;
                                    }
                                    try {
                                      setRunning(true);
                                      addLog("Starting Smart Deep Scrape via ADB...");
                                      const targetLocParam = adbLocation.trim() ? `&target_location=${encodeURIComponent(adbLocation.trim())}` : '';
                                      const res = await fetch(`${LOCAL_API}/adb/smart-scrape?state=${state}&district=${city}&main_category=${category}&scrolls=${maxEntries}${targetLocParam}`, { method: 'POST' });
                                      const data = await res.json();
                                      if (data.status === 'started') {
                                        toast.success(data.message);
                                        addLog(`[Smart Scrape] ${data.message}`);
                                      } else {
                                        throw new Error(data.detail || data.message || "Failed to start");
                                      }
                                    } catch (e: any) {
                                      setRunning(false);
                                      toast.error(e.message);
                                      addLog(`[Smart Scrape] Error: ${e.message}`, false);
                                    }
                                  }} 
                                  disabled={running}
                                  className="w-full h-10 text-white font-medium shadow-brand text-xs bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700" 
                                >
                                  🚀 Deep Smart Scrape
                                </Button>
                              </div>
                            </div>

                            <div className="border-t pt-4 space-y-3">
                              {/* Sub-section 2: Proxy Server & Traffic Routing */}
                              <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                                <Zap className="size-3.5 text-brand" />
                                2. Proxy & Traffic Routing
                              </h4>
                              <p className="text-xs text-muted-foreground leading-relaxed">
                                Enable intercept proxy to capture JustDial API payloads. If active, all your phone traffic will be routed to the cloud proxy automatically.
                              </p>
                              
                              <div className="grid grid-cols-2 gap-3 bg-background/50 p-3 rounded-lg ring-1 ring-border text-xs">
                                <div>
                                  <span className="text-muted-foreground">Proxy Server Status:</span>
                                  <span className={`ml-1.5 font-bold ${proxyRunning ? 'text-emerald-500' : 'text-red-500'}`}>
                                    {proxyRunning ? 'RUNNING (Port 8089)' : 'STOPPED'}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Phone Traffic Route:</span>
                                  <span className={`ml-1.5 font-bold ${phoneProxy === 'Disconnected' ? 'text-amber-500' : phoneProxy === 'None' ? 'text-muted-foreground' : 'text-emerald-500'}`}>
                                    {phoneProxy === 'Disconnected' ? 'Phone Offline' : phoneProxy === 'None' ? 'Direct (None)' : `Routed to ${phoneProxy}`}
                                  </span>
                                </div>
                              </div>

                              <Button 
                                onClick={toggleProxyRouting} 
                                disabled={proxyToggling}
                                className={`w-full h-10 text-white font-medium shadow-brand text-xs ${proxyRunning ? 'bg-red-600 hover:bg-red-700' : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700'}`}
                              >
                                {proxyToggling ? (
                                  <><RefreshCw className="size-4 mr-2 animate-spin" />Configuring Proxy...</>
                                ) : proxyRunning ? (
                                  <><Square className="size-4 mr-2" />Stop Proxy Routing</>
                                ) : (
                                  <><Play className="size-4 mr-2" />Start Proxy Routing</>
                                )}
                              </Button>
                            </div>

                            <div className="border-t pt-4 space-y-3">
                              {/* Sub-section 3: JSON Ingestion */}
                              <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                                <Database className="size-3.5 text-brand" />
                                3. Ingest Captured Payload
                              </h4>
                            <p className="text-xs text-muted-foreground">
                              Paste the JSON response intercepted by HTTP Toolkit from the JustDial mobile app. 
                            </p>
                            <textarea
                              value={emulatorJson}
                              onChange={(e) => setEmulatorJson(e.target.value)}
                              placeholder='{"results": {"columns": [...], "data": [...]}}'
                              className="w-full h-32 rounded-lg p-3 text-sm bg-background ring-1 ring-border outline-none focus:ring-brand font-mono resize-y"
                            />
                            <Button 
                              onClick={ingestEmulatorJson} 
                              disabled={ingestingJson || !emulatorJson.trim()} 
                              className="w-full h-10 text-white font-medium shadow-brand" 
                              style={{ background: (ingestingJson || !emulatorJson.trim()) ? undefined : "var(--gradient-brand)" }}
                            >
                              <Database className="size-4 mr-2" />{ingestingJson ? "Processing..." : "Ingest JSON"}
                            </Button>
                          </div>

                          <div className="border-t pt-4 space-y-3">
                            {/* Sub-section 3: Bulk Folder Upload */}
                            <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                              <Download className="size-3.5 text-brand" />
                              3. Bulk Ingest Saved Folder
                            </h4>
                            <p className="text-xs text-muted-foreground">
                              Upload all JSON files saved in the <code>JustDial_JSONs</code> folder on your Desktop.
                            </p>
                            <Button 
                              onClick={ingestSavedFolder} 
                              disabled={ingestingJson} 
                              className="w-full h-10 text-white font-medium shadow-brand" 
                              style={{ background: ingestingJson ? undefined : "var(--gradient-brand)" }}
                            >
                              <Download className="size-4 mr-2" />{ingestingJson ? "Ingesting..." : "Bulk Ingest Saved Folder"}
                            </Button>
                          </div>

                          <div className="border-t pt-4 space-y-3">
                            {/* Sub-section 5: Compiled Scrape JSONs Browser */}
                            <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                              <FileSpreadsheet className="size-3.5 text-brand" />
                              5. Compiled Scrape JSONs
                            </h4>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                              Browse, inspect, and download completed JSON compilation sheets from your ADB smart runs.
                            </p>

                            {loadingJsons ? (
                              <div className="text-xs text-muted-foreground animate-pulse py-2 flex items-center justify-center gap-2">
                                <RefreshCw className="size-3.5 animate-spin" /> Loading compiled sheets...
                              </div>
                            ) : compiledJsons.length === 0 ? (
                              <div className="text-xs text-muted-foreground text-center py-4 bg-background/30 rounded-lg border border-dashed border-border">
                                No compiled JSON files found. Run a Deep Smart Scrape first.
                              </div>
                            ) : (
                              <div className="max-h-60 overflow-y-auto ring-1 ring-border rounded-lg bg-background/50 divide-y divide-border">
                                {compiledJsons.map((file) => (
                                  <div key={file.filename} className="flex items-center justify-between p-2.5 text-xs">
                                    <div className="min-w-0 flex-1 pr-3">
                                      <div className="font-semibold text-foreground truncate">{file.filename}</div>
                                      <div className="text-[10px] text-muted-foreground mt-0.5">
                                        {(file.size_bytes / 1024).toFixed(1)} KB • {new Date(file.modified * 1000).toLocaleString()}
                                      </div>
                                    </div>
                                    <div className="flex gap-1.5 shrink-0">
                                      <button 
                                        onClick={() => viewJsonFile(file.filename)}
                                        className="p-1.5 rounded bg-muted hover:bg-muted/80 text-foreground transition-colors" 
                                        title="View JSON"
                                      >
                                        <Search className="size-3.5" />
                                      </button>
                                      <a 
                                        href={`${API}/compiled-jsons/${file.filename}`}
                                        download
                                        target="_blank"
                                        className="p-1.5 rounded bg-brand/10 hover:bg-brand/20 text-brand transition-colors" 
                                        title="Download"
                                      >
                                        <Download className="size-3.5" />
                                      </a>
                                      <button 
                                        onClick={() => deleteJsonFile(file.filename)}
                                        className="p-1.5 rounded bg-red-500/10 hover:bg-red-500/20 text-red-500 transition-colors" 
                                        title="Delete"
                                      >
                                        <Trash2 className="size-3.5" />
                                      </button>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                            <div className="flex justify-end pt-1">
                              <Button 
                                onClick={fetchCompiledJsons}
                                variant="secondary" 
                                size="sm" 
                                className="h-8 text-[11px]"
                              >
                                <RefreshCw className="size-3 mr-1.5" /> Refresh List
                              </Button>
                            </div>
                          </div>
                        </section>
                      )}

                      {/* Single URL */}
                      <section className="p-6 rounded-2xl ring-1 ring-border bg-card shadow-elegant space-y-4">
                        <div className="flex items-center gap-2">
                          <Link2 className="size-4 text-brand" />
                          <h3 className="text-base font-semibold">Single URL Scraper</h3>
                        </div>
                        <FormField label="JustDial URL">
                          <input type="text" value={singleUrl} onChange={(e) => setSingleUrl(e.target.value)} placeholder="https://www.justdial.com/..." className="w-full h-10 rounded-lg px-3 text-sm font-mono bg-background ring-1 ring-border outline-none focus:ring-brand transition-all placeholder:text-muted-foreground" />
                        </FormField>
                        <Button onClick={scrapeUrl} className="w-full h-10 text-white font-medium shadow-brand" style={{ background: "var(--gradient-brand)" }}>
                          <Link2 className="size-4 mr-2" />Scrape This URL
                        </Button>
                      </section>
                    </div>
                  </div>

                  {/* Activity Log — modal trigger, full width */}
                  <button
                    onClick={() => setLogModalOpen(true)}
                    className="w-full rounded-2xl ring-1 ring-border bg-card shadow-elegant px-5 py-3 flex items-center gap-3 hover:bg-accent/30 transition-colors"
                  >
                    <Activity className="size-4 text-brand shrink-0" />
                    <span className="text-sm font-semibold">Activity Log</span>
                    <span className="text-xs text-muted-foreground font-mono">{log.length} entries</span>
                    {running && <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />}
                    <span className="ml-auto text-[10px] text-muted-foreground uppercase tracking-widest">Click to view →</span>
                  </button>
                </>
              ) : (
                /* ══ DEFAULT COMPACT SCRAPER LAYOUT ══ */
                <div className="grid grid-cols-2 gap-2 flex-1 min-h-0">
                  {/* Location & Category */}
                  <section className="p-3 rounded-xl ring-1 ring-border bg-card shadow-elegant flex flex-col gap-2 flex-1 min-h-0">
                    <div className="flex items-center gap-2">
                      <MapPin className="size-3.5 text-brand" />
                      <h3 className="text-xs font-semibold tracking-tight">Location & Category</h3>
                      {fetchingCount && <span className="text-[9px] text-muted-foreground animate-pulse">checking...</span>}
                      {listingCount && !fetchingCount && (
                        <span className="ml-auto text-[9px] font-mono px-1.5 py-0.5 rounded-full bg-brand/10 text-brand font-semibold">{listingCount}</span>
                      )}
                    </div>

                    {/* Search */}
                    <div className="flex items-center gap-2 h-8 px-2.5 rounded-lg ring-1 ring-border bg-background focus-within:ring-brand transition-all">
                      <Search className="size-3 text-muted-foreground shrink-0" />
                      <input
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search businesses..."
                        className="bg-transparent text-xs flex-1 outline-none placeholder:text-muted-foreground"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <FormField label="State / UT"><StyledSelect value={state} onChange={setState} options={STATES} /></FormField>
                      <FormField label="District / City"><StyledSelect value={city} onChange={setCity} options={cities.length ? cities : ["—"]} /></FormField>
                      <FormField label="Main Category">
                        <StyledSelect
                          value={category}
                          onChange={setCategory}
                          options={CATEGORIES}
                          counts={Object.fromEntries(categoryCounts.map((c) => [c.category, c.count]))}
                        />
                      </FormField>
                      <FormField label="Subcategory">
                        <StyledSelect
                          value={subcategory}
                          onChange={setSubcategory}
                          options={getSubcategoryOptions()}
                        />
                      </FormField>
                      <FormField label="Engine">
                        <StyledSelect
                          value={
                            engine === "api" ? "⚡ API (Chrome)" : 
                            engine === "api_edge" ? "⚡ API (Edge)" : 
                            engine === "selenium" ? "Chrome" : 
                            engine === "edge" ? "Edge" : 
                            engine === "playwright" ? "Playwright (Chrome)" : 
                            engine === "playwright_edge" ? "Playwright (Edge)" : 
                            engine === "emulator" ? "📱 Mobile" : 
                            "Playwright (Chrome)"
                          }
                          onChange={(v) => {
                            if (v.includes("Chrome)")) {
                              if (v.includes("API")) setEngine("api");
                              else setEngine("playwright");
                            }
                            else if (v.includes("Edge)")) {
                              if (v.includes("API")) setEngine("api_edge");
                              else setEngine("playwright_edge");
                            }
                            else if (v === "Chrome") setEngine("selenium");
                            else if (v === "Edge") setEngine("edge");
                            else if (v.includes("Mobile")) setEngine("emulator");
                          }}
                          options={["⚡ API (Chrome)", "⚡ API (Edge)", "Chrome", "Edge", "Playwright (Chrome)", "Playwright (Edge)", "📱 Mobile"]}
                        />
                      </FormField>
                      <FormField label="Max Entries">
                        <input
                          type="number" min={1} max={500} value={maxEntries}
                          onChange={(e) => setMaxEntries(Math.max(1, Number(e.target.value)))}
                          className="w-full h-8 rounded-lg px-2 text-xs bg-background ring-1 ring-border outline-none focus:ring-brand transition-all"
                        />
                      </FormField>
                    </div>

                    {/* Check Listings button */}
                    <Button
                      onClick={checkListings}
                      disabled={checkingListings || !city}
                      variant="outline"
                      size="sm"
                      className="w-full h-8 text-xs"
                    >
                      {checkingListings
                        ? <><RefreshCw className="size-3 mr-1.5 animate-spin" />Checking...</>
                        : <><Search className="size-3 mr-1.5" />Check Listings in {city || "..."}</>
                      }
                    </Button>
                    {/* Fast Mode Checkbox */}
                    <div className="flex items-center gap-1.5 mt-2">
                      <Checkbox id="fastModeSm" checked={fastMode} onCheckedChange={(checked) => setFastMode(!!checked)} />
                      <label htmlFor="fastModeSm" className="text-[10px] font-semibold text-muted-foreground cursor-pointer select-none">
                        ⚡ Fast Mode (URLs only)
                      </label>
                    </div>
                  </section>

                  {/* Right column: Controls + Single URL + Activity Log */}
                  <div className="flex flex-col gap-2 min-h-0">
                    <section className="p-3 rounded-xl ring-1 ring-border bg-card shadow-elegant space-y-2">
                      <div className="flex items-center justify-between">
                        <h3 className="text-xs font-semibold tracking-tight">Controls</h3>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] text-muted-foreground">Status:</span>
                          <span className={cn("text-[10px] font-semibold", statusColor)}>{status}</span>
                          {running && <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />}
                        </div>
                      </div>
                      {running && (
                        <div className="space-y-1">
                          <div className="flex justify-between text-[10px]">
                            <span className="text-muted-foreground">Processing...</span>
                            <span className="text-brand font-mono">{Math.round(progress)}%</span>
                          </div>
                          <Progress value={progress} className="h-1" />
                        </div>
                      )}
                      <div className="grid grid-cols-3 gap-1.5">
                        <Button onClick={startScraping} disabled={running} size="sm" className="h-8 text-white text-xs font-medium shadow-brand" style={{ background: running ? undefined : "var(--gradient-brand)" }}>
                          <Play className="size-3 mr-1" />{running ? "Running" : "Start"}
                        </Button>
                        <Button onClick={stopScraping} disabled={!running} variant="outline" size="sm" className="h-8 text-xs">
                          <Square className="size-3 mr-1" />Stop
                        </Button>
                        <Button onClick={refreshCategories} variant="secondary" size="sm" className="h-8 text-xs">
                          <RefreshCw className="size-3 mr-1" />Refresh
                        </Button>
                      </div>
                    </section>

                    {/* Emulator Control Center (Mobile/Compact Layout) */}
                    {engine === "emulator" && (
                      <section className="p-3 rounded-xl ring-1 ring-border bg-card shadow-elegant space-y-3">
                        <div className="flex items-center gap-2 border-b pb-1.5">
                          <Database className="size-3.5 text-brand" />
                          <h3 className="text-xs font-semibold tracking-tight">📱 Emulator Control Center</h3>
                        </div>

                        {/* Remote Search Trigger */}
                        <div className="space-y-1.5">
                          <h4 className="text-[10px] font-semibold text-foreground flex items-center gap-1">
                            <Play className="size-3 text-brand" />
                            1. Remote Emulator Search
                          </h4>
                          <div className="flex gap-2 items-end">
                            <div className="flex-1">
                              <FormField label="Target Location (PIN or Town)">
                                <input 
                                  type="text" 
                                  value={adbLocation} 
                                  onChange={(e) => setAdbLocation(e.target.value)} 
                                  className="w-full h-8 rounded-lg px-2 text-xs bg-background ring-1 ring-border outline-none focus:ring-brand" 
                                  placeholder="e.g. 671315" 
                                />
                              </FormField>
                            </div>
                          <div className="flex flex-col gap-2 mt-2">
                            <Button 
                              onClick={triggerAdbSearch} 
                              disabled={running}
                              size="sm"
                              className="w-full h-8 text-white font-medium shadow-brand text-[10px]" 
                              style={{ background: running ? undefined : "var(--gradient-brand)" }}
                            >
                              {running ? "Search..." : "Manual PIN Search"}
                            </Button>
                            <Button 
                              onClick={async () => {
                                  if (!state || !city || !category) {
                                    toast.error("Please select State, District, and Category first!");
                                    return;
                                  }
                                  try {
                                    setRunning(true);
                                    addLog("Starting Smart Deep Scrape via ADB...");
                                    const targetLocParam = adbLocation.trim() ? `&target_location=${encodeURIComponent(adbLocation.trim())}` : '';
                                    const res = await fetch(`${LOCAL_API}/adb/smart-scrape?state=${state}&district=${city}&main_category=${category}&scrolls=${maxEntries}${targetLocParam}`, { method: 'POST' });
                                    const data = await res.json();
                                    if (data.status === 'started') {
                                      toast.success(data.message);
                                      addLog(`[Smart Scrape] ${data.message}`);
                                    } else {
                                      throw new Error(data.detail || data.message || "Failed to start");
                                    }
                                  } catch (e: any) {
                                    setRunning(false);
                                    toast.error(e.message);
                                    addLog(`[Smart Scrape] Error: ${e.message}`, false);
                                  }
                                }}
                              disabled={running}
                              size="sm"
                              className="w-full h-8 text-white font-medium shadow-brand text-[10px] bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700" 
                            >
                              🚀 Deep Smart Scrape
                            </Button>
                          </div>
                        </div>
                      </div>

                        {/* JSON Ingestion */}
                        <div className="border-t pt-2 space-y-1.5">
                          <h4 className="text-[10px] font-semibold text-foreground flex items-center gap-1">
                            <Database className="size-3 text-brand" />
                            2. Ingest Captured/Saved JSON
                          </h4>
                          <textarea
                            value={emulatorJson}
                            onChange={(e) => setEmulatorJson(e.target.value)}
                            placeholder='{"results": {"columns": [...], "data": [...]}}'
                            className="w-full h-20 rounded-lg p-2 text-[10px] bg-background ring-1 ring-border outline-none focus:ring-brand font-mono resize-y"
                          />
                          <div className="space-y-1.5">
                            <Button 
                              onClick={ingestEmulatorJson} 
                              disabled={ingestingJson}
                              size="sm"
                              className="w-full bg-brand text-white shadow-brand h-8 text-[11px]" 
                              style={{ background: "var(--gradient-brand)" }}
                            >
                              {ingestingJson ? "Ingesting..." : "Ingest Pasted JSON"}
                            </Button>
                            <Button 
                              onClick={ingestSavedFolder} 
                              disabled={ingestingJson}
                              size="sm"
                              className="w-full bg-brand text-white shadow-brand h-8 text-[11px]" 
                              style={{ background: "var(--gradient-brand)" }}
                            >
                              {ingestingJson ? "Ingesting..." : "Bulk Ingest Desktop Folder"}
                            </Button>
                          </div>
                        </div>

                        {/* Compact Proxy Routing controls */}
                        <div className="border-t pt-2 space-y-1.5">
                          <h4 className="text-[10px] font-semibold text-foreground flex items-center gap-1">
                            <Zap className="size-3 text-brand" />
                            4. Proxy & Traffic Routing
                          </h4>
                          <p className="text-[9px] text-muted-foreground leading-relaxed">
                            Route phone traffic through the cloud proxy to auto-capture data.
                          </p>
                          
                          <div className="grid grid-cols-2 gap-2 bg-background/50 p-2 rounded-lg ring-1 ring-border text-[9px]">
                            <div>
                              <span className="text-muted-foreground">Server:</span>
                              <span className={`ml-1 font-bold ${proxyRunning ? 'text-emerald-500' : 'text-red-500'}`}>
                                {proxyRunning ? 'RUNNING' : 'STOPPED'}
                              </span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">Phone:</span>
                              <span className={`ml-1 font-bold ${phoneProxy === 'Disconnected' ? 'text-amber-500' : phoneProxy === 'None' ? 'text-muted-foreground' : 'text-emerald-500'} truncate block`}>
                                {phoneProxy === 'Disconnected' ? 'Offline' : phoneProxy === 'None' ? 'Direct' : 'Routed'}
                              </span>
                            </div>
                          </div>

                          <Button 
                            onClick={toggleProxyRouting} 
                            disabled={proxyToggling}
                            size="sm"
                            className={`w-full h-8 text-[10px] text-white font-medium shadow-brand ${proxyRunning ? 'bg-red-600 hover:bg-red-700' : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700'}`}
                          >
                            {proxyToggling ? "Configuring..." : proxyRunning ? "Stop Proxy Routing" : "Start Proxy Routing"}
                          </Button>
                        </div>

                        {/* Compact Compiled Scrape JSONs Browser */}
                        <div className="border-t pt-2 space-y-1.5">
                          <h4 className="text-[10px] font-semibold text-foreground flex items-center gap-1">
                            <FileSpreadsheet className="size-3 text-brand" />
                            5. Compiled Scrape JSONs
                          </h4>

                          {loadingJsons ? (
                            <div className="text-[9px] text-muted-foreground animate-pulse py-1 text-center">
                              Loading compiled sheets...
                            </div>
                          ) : compiledJsons.length === 0 ? (
                            <div className="text-[9px] text-muted-foreground text-center py-2 bg-background/30 rounded border border-dashed border-border">
                              No compiled JSON files found.
                            </div>
                          ) : (
                            <div className="max-h-36 overflow-y-auto ring-1 ring-border rounded bg-background/50 divide-y divide-border">
                              {compiledJsons.map((file) => (
                                <div key={file.filename} className="flex items-center justify-between p-1.5 text-[9px]">
                                  <div className="min-w-0 flex-1 pr-2 truncate">
                                    <div className="font-semibold text-foreground truncate">{file.filename}</div>
                                    <div className="text-[8px] text-muted-foreground mt-0.5">
                                      {(file.size_bytes / 1024).toFixed(1)} KB
                                    </div>
                                  </div>
                                  <div className="flex gap-1 shrink-0">
                                    <button 
                                      onClick={() => viewJsonFile(file.filename)}
                                      className="p-1 rounded bg-muted hover:bg-muted/80 text-foreground transition-colors"
                                    >
                                      <Search className="size-3" />
                                    </button>
                                    <a 
                                      href={`${API}/compiled-jsons/${file.filename}`}
                                      download
                                      target="_blank"
                                      className="p-1 rounded bg-brand/10 hover:bg-brand/20 text-brand transition-colors"
                                    >
                                      <Download className="size-3" />
                                    </a>
                                    <button 
                                      onClick={() => deleteJsonFile(file.filename)}
                                      className="p-1 rounded bg-red-500/10 hover:bg-red-500/20 text-red-500 transition-colors"
                                    >
                                      <Trash2 className="size-3" />
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                          <div className="flex justify-end">
                            <Button 
                              onClick={fetchCompiledJsons}
                              variant="secondary" 
                              size="sm" 
                              className="h-6 text-[9px]"
                            >
                              <RefreshCw className="size-2.5 mr-1" /> Refresh
                            </Button>
                          </div>
                        </div>
                      </section>
                    )}

                    <section className="p-3 rounded-xl ring-1 ring-border bg-card shadow-elegant space-y-2">
                      <div className="flex items-center gap-2">
                        <Link2 className="size-3.5 text-brand" />
                        <h3 className="text-xs font-semibold tracking-tight">Single URL Scraper</h3>
                      </div>
                      <FormField label="JustDial URL">
                        <input type="text" value={singleUrl} onChange={(e) => setSingleUrl(e.target.value)} placeholder="https://www.justdial.com/..." className="w-full h-7 rounded-lg px-2 text-[11px] font-mono bg-background ring-1 ring-border outline-none focus:ring-brand transition-all placeholder:text-muted-foreground" />
                      </FormField>
                      <Button onClick={scrapeUrl} size="sm" className="w-full h-8 text-white text-xs font-medium shadow-brand" style={{ background: "var(--gradient-brand)" }}>
                        <Link2 className="size-3 mr-1" />Scrape This URL
                      </Button>
                    </section>

                    {/* Activity Log — modal trigger, grows to fill remaining space */}
                    <button
                      onClick={() => setLogModalOpen(true)}
                      className="rounded-xl ring-1 ring-border bg-card shadow-elegant px-3 py-2 flex items-center gap-2 hover:bg-accent/30 transition-colors w-full flex-1"
                    >
                      <Activity className="size-3.5 text-brand shrink-0" />
                      <span className="text-xs font-semibold">Activity Log</span>
                      <span className="text-[10px] text-muted-foreground font-mono">{log.length} entries</span>
                      {running && <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />}
                      <span className="ml-auto text-[9px] text-muted-foreground uppercase tracking-widest">View →</span>
                    </button>
                  </div>
                </div>
              )
            )}

            {/* ── LISTINGS QUEUE TAB ── */}
            {activeTab === "listings" && (
              <ListingsManager 
                API={API} 
                CITIES={CITIES} 
                SUBCATEGORIES={SUBCATEGORIES} 
                states={STATES} 
              />
            )}

            {/* ── DASHBOARD TAB ── */}
            {activeTab === "dashboard" && (
              rows.length === 0 ? (
                <div className="rounded-xl ring-1 ring-border bg-card shadow-elegant p-12 text-center">
                  <Database className="size-8 text-muted-foreground/30 mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground">No data yet — run a scrape from the Scraper tab first.</p>
                  <Button onClick={() => setActiveTab("scraper")} size="sm" className="mt-3 text-white shadow-brand" style={{ background: "var(--gradient-brand)" }}>Go to Scraper</Button>
                </div>
              ) : (
                <section className="rounded-xl ring-1 ring-border bg-card overflow-hidden shadow-elegant">
                  <div className="px-4 py-3 border-b border-border flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <h3 className="text-xs font-semibold">Scraped Results</h3>
                      <span className="text-[10px] text-muted-foreground">
                        {filtered.length} results
                        {selected.size > 0 && <span className="text-brand"> · {selected.size} selected</span>}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {selected.size > 0 && (
                        <Button variant="destructive" size="sm" onClick={() => setConfirmOpen(true)} className="h-8 px-3">
                          <Trash2 className="size-3.5 mr-1.5" />Delete ({selected.size})
                        </Button>
                      )}
                      <Button
                        size="sm"
                        className="h-8 px-3 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white"
                        onClick={() => exportData("csv")}
                      >
                        <Download className="size-3.5 mr-1.5" />Export CSV
                      </Button>
                      <Button
                        size="sm"
                        className="h-8 px-3 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white"
                        onClick={() => exportData("xlsx")}
                      >
                        <FileSpreadsheet className="size-3.5 mr-1.5" />Export Excel
                      </Button>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-muted/50 border-b border-border">
                        <tr className="text-[9px] uppercase tracking-widest text-muted-foreground">
                          <th className="p-3 w-8"><Checkbox checked={selected.size > 0 && selected.size === filtered.length} onCheckedChange={toggleAll} /></th>
                          <SortTh label="Business Name" k="name" sortKey={sortKey} dir={sortDir} onClick={sort} />
                          <SortTh label="Category" k="category" sortKey={sortKey} dir={sortDir} onClick={sort} />
                          <SortTh label="Location" k="location" sortKey={sortKey} dir={sortDir} onClick={sort} />
                          <SortTh label="Phone" k="phone" sortKey={sortKey} dir={sortDir} onClick={sort} />
                          <SortTh label="Rating" k="rating" sortKey={sortKey} dir={sortDir} onClick={sort} />
                          <th className="p-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filtered.map((r, i) => (
                          <tr
                            key={r.id}
                            onClick={() => openDetail(r)}
                            className={cn("border-b border-border/60 transition-colors hover:bg-accent/50 cursor-pointer", i % 2 === 1 && "bg-muted/20", selected.has(r.id) && "bg-brand/5")}
                          >
                            <td className="p-3" onClick={(e) => e.stopPropagation()}><Checkbox checked={selected.has(r.id)} onCheckedChange={() => toggleRow(r.id)} /></td>
                            <td className="p-3 font-medium">
                              <span className="hover:text-brand transition-colors">{r.name}</span>
                            </td>
                            <td className="p-3">
                              <span className="px-1.5 py-0.5 bg-brand/10 text-brand text-[9px] font-bold uppercase rounded-full">{r.category}</span>
                            </td>
                            <td className="p-3 text-muted-foreground">
                              {r.location}
                              {r.latitude && r.longitude && (
                                <div className="text-[9px] mt-0.5 font-mono opacity-70">
                                  {Number(r.latitude).toFixed(4)}, {Number(r.longitude).toFixed(4)}
                                </div>
                              )}
                            </td>
                            <td className="p-3 font-mono text-[10px] text-muted-foreground">{r.phone}</td>
                            <td className="p-3 font-mono text-[10px]">
                              {r.rating.toFixed(1)} <span className="text-muted-foreground">({r.reviews})</span>
                            </td>
                            <td className="p-3 text-right" onClick={(e) => e.stopPropagation()}>
                              <div className="flex items-center justify-end gap-0.5">
                                <button onClick={() => openDetail(r)} className="size-7 rounded hover:bg-accent flex items-center justify-center text-muted-foreground hover:text-brand transition-colors" title="View details">
                                  <ExternalLink className="size-3.5" />
                                </button>
                                <button onClick={() => setLightbox({ images: r.images.map(img => img.path), index: 0, name: r.name })} className="size-7 rounded hover:bg-accent flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors" title="View images">
                                  <ImageIcon className="size-3.5" />
                                </button>
                                <button onClick={() => { setSelected(new Set([r.id])); setConfirmOpen(true); }} className="size-7 rounded hover:bg-destructive/10 flex items-center justify-center text-muted-foreground hover:text-destructive transition-colors">
                                  <Trash2 className="size-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                        {filtered.length === 0 && (
                          <tr><td colSpan={7} className="p-8 text-center text-muted-foreground text-xs">No results match your search.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              )
            )}

            {/* ── DETAIL TAB ── */}
            {isDetailTab && (
              <DetailView
                business={(activeTab as { type: "detail"; business: Business }).business}
                onClose={() => closeDetail((activeTab as { type: "detail"; business: Business }).business.id)}
                onViewImages={(images, index, name) => setLightbox({ images, index, name })}
              />
            )}

            <div className="flex items-center gap-2 text-[9px] font-mono text-muted-foreground/50 justify-center py-3">
              <Activity className="size-3" />
              SYSTEM ONLINE · API healthy · backend.v3
            </div>
          </div>
        </div>
      </div>

      {/* Activity Log Modal */}
      {logModalOpen && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm rounded-xl" onClick={() => setLogModalOpen(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-[520px] max-w-[90%] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3 px-5 py-3 border-b border-border">
              <Activity className="size-4 text-brand shrink-0" />
              <span className="text-sm font-semibold">Activity Log</span>
              <span className="text-xs text-muted-foreground font-mono">{log.length} entries</span>
              {running && <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />}
              <button onClick={() => setLogModalOpen(false)} className="ml-auto size-6 flex items-center justify-center rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors">
                <X className="size-3.5" />
              </button>
            </div>
            <div ref={logRef} className="h-64 overflow-y-auto px-5 py-3 font-mono text-xs bg-muted/20 space-y-0.5">
              {log.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">No log entries yet.</p>
              ) : log.map((entry, i) => (
                <div key={i} className="flex gap-2 leading-6">
                  <span className="text-muted-foreground shrink-0">[{entry.time}]</span>
                  <span className={entry.ok ? "text-emerald-400" : "text-red-400"}>{entry.ok ? "✓" : "✗"}</span>
                  <span className="text-foreground/80">{entry.msg}</span>
                </div>
              ))}
            </div>
            <div className="px-5 py-2.5 border-t border-border flex items-center justify-between">
              <span className="text-[10px] font-mono text-muted-foreground/60">SYSTEM ONLINE · backend.v3</span>
              <button
                onClick={() => setLog([{ time: new Date().toLocaleTimeString("en-GB", { hour12: false }), ok: true, msg: "Log cleared." }])}
                className="text-[10px] text-muted-foreground hover:text-destructive transition-colors"
              >
                Clear log
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Category Listings Modal */}
      {categoryCountsModal && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm rounded-xl" onClick={() => setCategoryCountsModal(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-80 overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
              <MapPin className="size-4 text-brand shrink-0" />
              <div>
                <span className="text-sm font-semibold">Listings in {city}</span>
                <p className="text-[10px] text-muted-foreground">Click a category to select it</p>
              </div>
              <button onClick={() => setCategoryCountsModal(false)} className="ml-auto size-6 flex items-center justify-center rounded-md hover:bg-accent text-muted-foreground">
                <X className="size-3.5" />
              </button>
            </div>
            <div className="max-h-72 overflow-y-auto py-1">
              {categoryCounts.map((c) => (
                <button
                  key={c.category}
                  onClick={() => {
                    setCategory(c.category);
                    setSubcategory("");
                    setCategoryCountsModal(false);
                    toast.success(`Selected: ${c.category}`, { description: `${c.count} listings in ${city}` });
                  }}
                  className={cn(
                    "w-full flex items-center justify-between px-4 py-2.5 text-xs hover:bg-accent transition-colors",
                    category === c.category && "bg-brand/10 text-brand"
                  )}
                >
                  <span className="font-medium">{c.category}</span>
                  <span className={cn(
                    "font-mono font-semibold px-2 py-0.5 rounded-full text-[10px]",
                    c.count !== "—" ? "bg-brand/10 text-brand" : "text-muted-foreground"
                  )}>{c.count}</span>
                </button>
              ))}
            </div>
            <div className="px-4 py-2.5 border-t border-border text-[10px] text-muted-foreground">
              Select a category then click Start Scraping
            </div>
          </div>
        </div>
      )}

      {/* Delete dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <div className="size-12 rounded-full bg-destructive/10 text-destructive flex items-center justify-center mb-2"><Trash2 className="size-5" /></div>
            <DialogTitle>Delete {selected.size} record{selected.size === 1 ? "" : "s"}?</DialogTitle>
            <DialogDescription>This permanently removes the selected businesses including all scraped images and metadata. This cannot be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={confirmBulkDelete}><Trash2 className="size-4 mr-2" />Delete permanently</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Compiled JSON Viewer Modal */}
      <Dialog open={isJsonModalOpen} onOpenChange={setIsJsonModalOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] flex flex-col p-6">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold truncate flex items-center gap-2">
              <FileSpreadsheet className="size-4.5 text-brand" />
              Viewing: {viewingJsonFilename}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto mt-4 p-4 rounded-lg bg-zinc-950 text-zinc-100 font-mono text-xs leading-relaxed border border-border whitespace-pre-wrap select-all">
            {viewingJsonContent}
          </div>
          <DialogFooter className="mt-4 flex gap-2">
            <Button
              onClick={() => {
                if (viewingJsonContent) {
                  navigator.clipboard.writeText(viewingJsonContent);
                  toast.success("JSON copied to clipboard!");
                }
              }}
              variant="secondary"
              className="text-xs"
            >
              Copy to Clipboard
            </Button>
            <Button
              onClick={() => setIsJsonModalOpen(false)}
              className="text-xs text-white"
              style={{ background: "var(--gradient-brand)" }}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {lightbox && <Lightbox data={lightbox} onChange={setLightbox} onClose={() => setLightbox(null)} />}
    </div>
  );
}

/* ─── Detail View ──────────────────────────────────────────── */
function DetailView({ business: b, onClose, onViewImages }: { business: Business; onClose: () => void; onViewImages: (images: string[], index: number, name: string) => void }) {
  const [selectedImgTab, setSelectedImgTab] = useState("All");
  const [servicesSearch, setServicesSearch] = useState("");
  const [selectedServiceCat, setSelectedServiceCat] = useState("All");

  const categories = ["All", ...Array.from(new Set(b.images.map(img => img.category).filter(Boolean)))];

  const filteredImages = selectedImgTab === "All"
    ? b.images
    : b.images.filter(img => img.category === selectedImgTab);

  // Group amenities by category
  const groupedAmenities = (b.amenities || []).reduce((acc, curr) => {
    if (!acc[curr.category]) {
      acc[curr.category] = [];
    }
    if (curr.value && !acc[curr.category].includes(curr.value)) {
      acc[curr.category].push(curr.value);
    }
    return acc;
  }, {} as Record<string, string[]>);

  const amenityCategories = Object.keys(groupedAmenities);

  // Filter based on search and selected category
  const filteredGrouped = Object.entries(groupedAmenities).reduce((acc, [cat, vals]) => {
    if (selectedServiceCat !== "All" && cat !== selectedServiceCat) return acc;
    const filteredVals = vals.filter(v => v.toLowerCase().includes(servicesSearch.toLowerCase()));
    if (filteredVals.length > 0) {
      acc[cat] = filteredVals;
    }
    return acc;
  }, {} as Record<string, string[]>);

  return (
    <div className="space-y-6 animate-entrance">
      {/* Header card */}
      <section className="p-6 rounded-2xl ring-1 ring-border bg-card shadow-elegant">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">{b.name}</h2>
            <span className="inline-block mt-1.5 px-2.5 py-0.5 bg-brand/10 text-brand text-xs font-bold uppercase rounded-full">{b.category}</span>
          </div>
          <Button variant="destructive" size="sm" onClick={onClose} className="h-8 shrink-0">
            <X className="size-3.5 mr-1.5" />Close
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <DetailRow icon={<Star className="size-4 text-amber-400" />} label="Rating">
            <span className="font-semibold">{b.rating.toFixed(1)}</span>
            <span className="text-muted-foreground text-xs ml-1">({b.reviews} reviews)</span>
          </DetailRow>
          <DetailRow icon={<MessageCircle className="size-4 text-brand" />} label="WhatsApp">
            <a href={`https://wa.me/${b.whatsapp.replace(/\s/g, "")}`} target="_blank" rel="noreferrer" className="text-brand hover:underline font-mono text-sm">{b.whatsapp}</a>
          </DetailRow>
          <DetailRow icon={<MapPin className="size-4 text-brand" />} label="Address">
            <span className="text-sm">{b.address}</span>
          </DetailRow>
          <DetailRow icon={<Clock className="size-4 text-brand" />} label="Hours">
            <span className="text-sm">{b.hours}</span>
          </DetailRow>
          {b.latitude && b.longitude && (
            <DetailRow icon={<MapPin className="size-4 text-emerald-400" />} label="Coordinates">
              <span className="text-sm font-mono">{b.latitude}, {b.longitude}</span>
              <a 
                href={`https://www.google.com/maps/search/?api=1&query=${b.latitude},${b.longitude}`} 
                target="_blank" 
                rel="noreferrer" 
                className="text-brand hover:underline text-xs ml-3 inline-flex items-center gap-1 font-semibold"
              >
                Open Google Maps <ExternalLink className="size-3" />
              </a>
            </DetailRow>
          )}
          <DetailRow icon={<Link2 className="size-4 text-brand" />} label="JustDial URL" full>
            <div className="flex items-center gap-2 mt-1">
              <button
                onClick={() => { navigator.clipboard.writeText(b.justdialUrl); toast.success("Link copied!"); }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg ring-1 ring-border bg-card hover:bg-accent transition-colors"
              >
                <Download className="size-3.5" />
                Copy Link
              </button>
              {b.justdialUrl && (
                <a
                  href={b.justdialUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-white shadow-brand transition-colors"
                  style={{ background: "var(--gradient-brand)" }}
                >
                  <ExternalLink className="size-3.5" />
                  Open Link
                </a>
              )}
            </div>
          </DetailRow>
        </div>
      </section>

      {/* Quick Info & Services Checklist Section */}
      {b.amenities && b.amenities.length > 0 && (
        <section className="rounded-2xl ring-1 ring-border bg-card shadow-elegant overflow-hidden flex flex-col md:flex-row min-h-[300px]">
          {/* Left panel */}
          <div className="w-full md:w-60 border-r border-border bg-muted/10 p-4 shrink-0 flex flex-col gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 size-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search Services"
                value={servicesSearch}
                onChange={(e) => setServicesSearch(e.target.value)}
                className="w-full h-9 pl-9 pr-3 rounded-lg text-xs bg-background ring-1 ring-border outline-none focus:ring-brand transition-all placeholder:text-muted-foreground"
              />
            </div>
            
            <div className="flex flex-col gap-1">
              <button
                onClick={() => setSelectedServiceCat("All")}
                className={cn(
                  "w-full text-left px-3 py-2 rounded-lg text-xs font-semibold flex items-center justify-between transition-all",
                  selectedServiceCat === "All"
                    ? "bg-brand/10 text-brand ring-1 ring-brand/20"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
                )}
              >
                <span>All Categories</span>
                <span className="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded-full text-foreground/80">
                  {b.amenities.length}
                </span>
              </button>
              
              {amenityCategories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedServiceCat(cat)}
                  className={cn(
                    "w-full text-left px-3 py-2 rounded-lg text-xs font-semibold flex items-center justify-between transition-all",
                    selectedServiceCat === cat
                      ? "bg-brand/10 text-brand ring-1 ring-brand/20"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
                  )}
                >
                  <span className="truncate">{cat}</span>
                  <span className="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded-full text-foreground/80">
                    {groupedAmenities[cat].length}
                  </span>
                </button>
              ))}
            </div>
          </div>
          
          {/* Right panel */}
          <div className="flex-1 p-6 space-y-6">
            {Object.keys(filteredGrouped).length === 0 ? (
              <div className="h-full flex items-center justify-center text-muted-foreground text-xs py-12">
                No matching services or information found.
              </div>
            ) : (
              Object.entries(filteredGrouped).map(([cat, vals]) => (
                <div key={cat} className="space-y-3">
                  <h4 className="text-sm font-semibold tracking-tight text-foreground border-b border-border/40 pb-1.5">{cat}</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {vals.map((val) => (
                      <div
                        key={val}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg ring-1 ring-border/50 bg-background/50 hover:bg-muted/30 transition-colors"
                      >
                        <span className="size-4 rounded bg-brand/10 text-brand flex items-center justify-center text-[10px] font-bold shrink-0">✓</span>
                        <span className="text-xs font-medium text-foreground/80">{val}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      )}

      {/* Menu Items */}
      {b.menuItems.length > 0 && (
        <section className="rounded-2xl ring-1 ring-border bg-card overflow-hidden shadow-elegant">
          <div className="px-5 py-3 border-b border-border flex items-center gap-2">
            <UtensilsCrossed className="size-4 text-brand" />
            <h3 className="text-sm font-semibold">Menu Items</h3>
            <span className="text-xs text-muted-foreground ml-auto">{b.menuItems.length} items</span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b border-border">
              <tr className="text-[10px] uppercase tracking-widest text-muted-foreground">
                <th className="p-4 text-left">Item</th>
                <th className="p-4 text-left">Price</th>
                <th className="p-4 text-left">Veg?</th>
              </tr>
            </thead>
            <tbody>
              {b.menuItems.map((m, i) => (
                <tr key={i} className={cn("border-b border-border/60", i % 2 === 1 && "bg-muted/20")}>
                  <td className="p-4">{m.item}</td>
                  <td className="p-4 font-mono text-brand">{m.price}</td>
                  <td className="p-4">
                    {m.veg
                      ? <span className="flex items-center gap-1 text-emerald-400 text-xs font-medium"><span className="size-3 rounded-sm border-2 border-emerald-400 flex items-center justify-center text-[8px]">✓</span>Yes</span>
                      : <span className="flex items-center gap-1 text-red-400 text-xs font-medium"><span className="size-3 rounded-sm border-2 border-red-400 flex items-center justify-center text-[8px]">✗</span>No</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Scraped Images */}
      <section className="rounded-2xl ring-1 ring-border bg-card shadow-elegant overflow-hidden">
        <div className="px-5 py-3 border-b border-border flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <ImageIcon className="size-4 text-brand" />
            <h3 className="text-sm font-semibold">Scraped Images</h3>
            <span className="text-xs text-muted-foreground">{filteredImages.length} of {b.images.length} images</span>
          </div>
          <div className="flex flex-wrap gap-1 bg-muted/40 p-1 rounded-lg ring-1 ring-border/50">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedImgTab(cat)}
                className={cn(
                  "px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider rounded-md transition-all",
                  selectedImgTab === cat
                    ? "bg-brand text-white shadow-sm font-semibold"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/65"
                )}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
        <div className="p-5 grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredImages.map((img, i) => (
            <button
              key={i}
              onClick={() => onViewImages(filteredImages.map(x => x.path), i, b.name)}
              className="group relative aspect-video rounded-xl overflow-hidden ring-1 ring-border hover:ring-brand transition-all"
            >
              <img src={img.path} alt={`${b.name} image ${i + 1}`} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/35 transition-colors flex flex-col items-center justify-center p-2 text-center">
                <ImageIcon className="size-6 text-white opacity-0 group-hover:opacity-100 transition-opacity mb-1" />
                <span className="text-[10px] text-white bg-black/60 px-2 py-0.5 rounded-md uppercase tracking-wider font-semibold opacity-0 group-hover:opacity-100 transition-opacity">
                  {img.category}
                </span>
              </div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function DetailRow({ icon, label, children, full }: { icon: React.ReactNode; label: string; children: React.ReactNode; full?: boolean }) {
  return (
    <div className={cn("flex items-start gap-3", full && "md:col-span-2")}>
      <div className="shrink-0 mt-0.5">{icon}</div>
      <div className="min-w-0">
        <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground mb-0.5">{label}</p>
        <div className="text-foreground">{children}</div>
      </div>
    </div>
  );
}

/* ─── Shared components ────────────────────────────────────── */
function NavItem({ icon, label, active, onClick, collapsed, dark }: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
  collapsed?: boolean;
  dark?: boolean;
}) {
  if (collapsed) {
    return (
      <button
        onClick={onClick}
        title={label}
        className={cn(
          "w-full flex items-center justify-center rounded-lg py-2.5 transition-all",
          dark
            ? active
              ? "bg-brand/20 text-brand"
              : "text-white/40 hover:text-white hover:bg-white/10"
            : active
              ? "bg-card text-brand ring-1 ring-border shadow-sm"
              : "text-muted-foreground hover:text-foreground hover:bg-sidebar-accent"
        )}
      >
        {icon}
      </button>
    );
  }
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-medium transition-all",
        active
          ? "bg-card text-foreground ring-1 ring-border shadow-sm"
          : "text-muted-foreground hover:text-foreground hover:bg-sidebar-accent"
      )}
    >
      <span className={cn("shrink-0", active && "text-brand")}>{icon}</span>
      <span className="truncate">{label}</span>
    </button>
  );
}

function StatCard({ label, value, trend, icon, live }: { label: string; value: string; trend: string; icon: React.ReactNode; live?: boolean }) {
  return (
    <div className="p-3 rounded-xl ring-1 ring-border bg-card shadow-elegant hover:ring-brand/30 transition-all">
      <div className="flex items-start justify-between mb-1.5">
        <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest leading-tight">{label}</span>
        <div className="size-5 rounded-md bg-brand/10 text-brand flex items-center justify-center shrink-0">{icon}</div>
      </div>
      <div className="text-lg font-semibold tracking-tight">{value}</div>
      <div className="flex items-center gap-1 mt-1">
        {live && <span className="size-1.5 rounded-full bg-success animate-pulse" />}
        <span className="text-[9px] font-medium text-muted-foreground truncate">{trend}</span>
      </div>
    </div>
  );
}

function StatCardLg({ label, value, trend, icon, live }: { label: string; value: string; trend: string; icon: React.ReactNode; live?: boolean }) {
  return (
    <div className="p-5 rounded-2xl ring-1 ring-border bg-card shadow-elegant hover:ring-brand/30 transition-all">
      <div className="flex items-start justify-between mb-3">
        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">{label}</span>
        <div className="size-8 rounded-lg bg-brand/10 text-brand flex items-center justify-center shrink-0">{icon}</div>
      </div>
      <div className="text-3xl font-semibold tracking-tight">{value}</div>
      <div className="flex items-center gap-1.5 mt-2">
        {live && <span className="size-1.5 rounded-full bg-success animate-pulse" />}
        <span className="text-xs font-medium text-muted-foreground">{trend}</span>
      </div>
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">{label}</label>
      {children}
    </div>
  );
}

function StyledSelect({ value, onChange, options }: { 
  value: string; 
  onChange: (v: string) => void; 
  options: (string | { label: string; value: string; indent?: number; parent?: string; hasChildren?: boolean })[]; 
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full h-8 rounded-lg px-2.5 text-xs bg-background ring-1 ring-border flex items-center justify-between gap-1 transition-all hover:ring-brand"
      >
        <span className="truncate">{value || "Select…"}</span>
        <ChevronDown className="size-3 text-muted-foreground shrink-0" />
      </button>
      <SelectModal open={open} value={value} options={options} onSelect={(v) => { onChange(v); setOpen(false); }} onClose={() => setOpen(false)} />
    </>
  );
}

function StyledSelectLg({ value, onChange, options }: { 
  value: string; 
  onChange: (v: string) => void; 
  options: (string | { label: string; value: string; indent?: number; parent?: string; hasChildren?: boolean })[]; 
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full h-10 rounded-lg px-3 text-sm bg-background ring-1 ring-border flex items-center justify-between gap-2 transition-all hover:ring-brand"
      >
        <span className="truncate">{value || "Select…"}</span>
        <ChevronDown className="size-3.5 text-muted-foreground shrink-0" />
      </button>
      <SelectModal open={open} value={value} options={options} onSelect={(v) => { onChange(v); setOpen(false); }} onClose={() => setOpen(false)} />
    </>
  );
}

function SelectModal({ open, value, options, onSelect, onClose }: {
  open: boolean;
  value: string;
  options: (string | { label: string; value: string; indent?: number; parent?: string; hasChildren?: boolean })[];
  onSelect: (v: string) => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) { setSearch(""); setCollapsedGroups(new Set()); setTimeout(() => inputRef.current?.focus(), 50); }
  }, [open]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  if (!open) return null;

  // Normalize options to object format
  const normalizedOptions = options.map(o => {
    if (typeof o === "string") {
      return { label: o, value: o, indent: 0 };
    }
    return o;
  });

  // Toggle collapse state for a parent group
  const toggleCollapse = (groupName: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent selection when expanding/collapsing
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupName)) {
        next.delete(groupName);
      } else {
        next.add(groupName);
      }
      return next;
    });
  };

  // Filter based on search and collapse state
  const filtered = normalizedOptions.filter((o) => {
    // If searching, show all matching regardless of collapse state
    if (search) {
      return o.label.toLowerCase().includes(search.toLowerCase());
    }
    
    // Check if any parent of this option is collapsed
    if (o.parent && collapsedGroups.has(o.parent)) {
      return false;
    }
    return true;
  });

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm rounded-xl" onClick={onClose}>
      <div className="bg-card border border-border rounded-2xl shadow-2xl w-80 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <span className="text-sm font-semibold">Select option</span>
          <button onClick={onClose} className="size-6 flex items-center justify-center rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors">
            <X className="size-3.5" />
          </button>
        </div>
        {/* Search */}
        <div className="px-3 py-2 border-b border-border">
          <div className="flex items-center gap-2 px-2 h-8 rounded-lg bg-background ring-1 ring-border">
            <Search className="size-3 text-muted-foreground shrink-0" />
            <input
              ref={inputRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search..."
              className="bg-transparent text-xs flex-1 outline-none placeholder:text-muted-foreground"
            />
          </div>
        </div>
        {/* Options */}
        <div className="max-h-60 overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <p className="px-4 py-3 text-xs text-muted-foreground">No results</p>
          ) : filtered.map((o) => {
            const indentStyle = { paddingLeft: `${16 + (o.indent || 0) * 16}px` };
            const isCollapsed = collapsedGroups.has(o.label);
            
            return (
              <div 
                key={o.value} 
                className="w-full flex items-center hover:bg-accent/60 transition-colors group"
                style={indentStyle}
              >
                {/* Collapse / Expand Toggle Button for parent categories */}
                {o.hasChildren ? (
                  <button
                    type="button"
                    onClick={(e) => toggleCollapse(o.label, e)}
                    className="size-5 flex items-center justify-center rounded hover:bg-accent text-muted-foreground hover:text-foreground shrink-0 mr-1"
                  >
                    <ChevronDown className={cn("size-3.5 transition-transform", isCollapsed && "-rotate-90")} />
                  </button>
                ) : (
                  <div className="size-5 shrink-0 mr-1" /> // Spacer for child alignment
                )}
                
                <button
                  type="button"
                  onClick={() => onSelect(o.value)}
                  className={cn(
                    "flex-1 text-left py-2 text-xs transition-colors flex items-center justify-between",
                    o.value === value && "text-brand font-semibold"
                  )}
                >
                  <span className="truncate">{o.label}</span>
                  {o.value === value && <span className="size-1.5 rounded-full bg-brand mr-4" />}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function SortTh({ label, k, sortKey, dir, onClick }: { label: string; k: keyof Business; sortKey: keyof Business; dir: "asc" | "desc"; onClick: (k: keyof Business) => void }) {
  const active = sortKey === k;
  return (
    <th className="p-4 font-medium">
      <button onClick={() => onClick(k)} className={cn("flex items-center gap-1 hover:text-foreground transition-colors", active && "text-brand")}>
        {label}{active && <span className="text-[8px]">{dir === "asc" ? "▲" : "▼"}</span>}
      </button>
    </th>
  );
}

function Lightbox({ data, onChange, onClose }: { data: { images: string[]; index: number; name: string }; onChange: (d: { images: string[]; index: number; name: string }) => void; onClose: () => void }) {
  const { images, index, name } = data;
  const prev = () => onChange({ ...data, index: (index - 1 + images.length) % images.length });
  const next = () => onChange({ ...data, index: (index + 1) % images.length });
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); if (e.key === "ArrowLeft") prev(); if (e.key === "ArrowRight") next(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, images.length]);
  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-6 animate-entrance">
      <button onClick={onClose} className="absolute top-5 right-5 size-10 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center" aria-label="Close"><X className="size-5" /></button>
      <button onClick={prev} className="absolute left-5 size-12 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center" aria-label="Previous"><ChevronLeft className="size-6" /></button>
      <button onClick={next} className="absolute right-5 size-12 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center" aria-label="Next"><ChevronRight className="size-6" /></button>
      <div className="max-w-5xl w-full max-h-full flex flex-col items-center gap-4">
        <img src={images[index]} alt={`${name} ${index + 1}`} className="max-h-[75vh] w-auto rounded-xl shadow-2xl object-contain" />
        <div className="text-center text-white">
          <div className="text-sm font-medium">{name}</div>
          <div className="text-xs text-white/60 font-mono mt-1">{index + 1} / {images.length}</div>
        </div>
      </div>
    </div>
  );
}
