import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Database, Search, Target, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

// Make sure to pass CITIES and SUBCATEGORIES from index.tsx or import them if exported
export default function ListingsManager({
  API,
  CITIES,
  SUBCATEGORIES,
  states,
}: {
  API: string;
  CITIES: Record<string, string[]>;
  SUBCATEGORIES: Record<string, string[]>;
  states: string[];
}) {
  const [state, setState] = useState(states[0] || "");
  const [district, setDistrict] = useState("All");
  const [mainCat, setMainCat] = useState("Restaurants");
  const [subCat, setSubCat] = useState("All");
  const [searchQuery, setSearchQuery] = useState("");

  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);
  const [totalScraped, setTotalScraped] = useState(0);
  const [totalAvailable, setTotalAvailable] = useState<number | null>(null);
  const [fetchingStats, setFetchingStats] = useState(false);
  const [data, setData] = useState<any[]>([]);

  const [targetPage, setTargetPage] = useState(1);
  const [scraping, setScraping] = useState(false);
  const [engine, setEngine] = useState("api");

  const [previewing, setPreviewing] = useState(false);
  const [previewData, setPreviewData] = useState<{name: string, phone: string}[] | null>(null);

  const districts = CITIES[state] || [];
  const subCategoriesList = SUBCATEGORIES[mainCat] || [];

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPage();
    }, 300);
    return () => clearTimeout(timer);
  }, [page, district, state, subCat, searchQuery, limit]);

  async function fetchPage() {
    try {
      const qs = new URLSearchParams({ page: page.toString(), limit: limit.toString() });
      if (state && state !== "All") qs.append("state", state);
      if (district && district !== "All") qs.append("district", district);
      if (subCat && subCat !== "All") qs.append("category", subCat);
      if (searchQuery) qs.append("search", searchQuery);

      const res = await fetch(`${API}/listings?${qs.toString()}`);
      if (res.ok) {
        const json = await res.json();
        setData(json.data || []);
        setTotalScraped(json.total_count || 0);
      }
    } catch (e) {
      console.error("Failed to fetch listings", e);
    }
  }

  async function handleFetchAvailable() {
    if (district === "All") {
      alert("Please select a specific District to fetch total available count from JustDial.");
      return;
    }
    
    const categoryToFetch = subCat === "All" ? mainCat : subCat;
    
    setFetchingStats(true);
    try {
      const res = await fetch(`${API}/listing-count?city=${district}&category=${categoryToFetch}`);
      if (res.ok) {
        const json = await res.json();
        setTotalAvailable(json.count);
      } else {
        alert("Failed to fetch counts.");
      }
    } catch (e) {
      console.error(e);
      alert("Error fetching counts.");
    } finally {
      setFetchingStats(false);
    }
  }

  async function handleTargetScrape() {
    if (scraping) return;
    setScraping(true);
    try {
      const qs = new URLSearchParams({
        state: state,
        district: district,
        main_cat: mainCat,
        subcat: subCat === "All" ? "" : subCat,
        start_page: targetPage.toString(),
        max_limit: "10",
        engine: engine,
      });

      await fetch(`${API}/scrape?${qs.toString()}`, {
        method: "POST",
      });
      alert(`Scraping triggered for page ${targetPage}!`);
    } catch (e) {
      console.error(e);
      alert("Failed to trigger scrape.");
    } finally {
      setScraping(false);
    }
  }

  async function handlePreviewPage() {
    if (previewing) return;
    setPreviewing(true);
    setPreviewData(null);
    try {
      const categoryToFetch = subCat === "All" ? mainCat : subCat;
      const res = await fetch(`${API}/preview-page?city=${district}&category=${categoryToFetch}&page=${targetPage}`);
      if (res.ok) {
        const json = await res.json();
        setPreviewData(json.data || []);
      } else {
        alert("Failed to preview page.");
      }
    } catch (e) {
      console.error(e);
      alert("Error previewing page.");
    } finally {
      setPreviewing(false);
    }
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto p-4 space-y-4">
      {/* Controls Top Bar */}
      <div className="bg-card rounded-xl p-4 ring-1 ring-border shadow-sm flex flex-wrap gap-4 items-end">
        <div className="space-y-1.5 flex-1 min-w-[150px]">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Search</label>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search Name or Phone..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
              className="w-full h-9 pl-9 pr-3 rounded-lg border border-input bg-transparent text-sm outline-none focus:ring-1 focus:ring-brand"
            />
          </div>
        </div>
        <div className="space-y-1.5 flex-1 min-w-[150px]">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">State</label>
          <select value={state} onChange={(e) => { setState(e.target.value); setDistrict("All"); setPage(1); }} className="w-full h-9 rounded-lg border border-input bg-transparent px-3 py-1 text-sm outline-none">
            {states.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="space-y-1.5 flex-1 min-w-[150px]">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">District</label>
          <select value={district} onChange={(e) => { setDistrict(e.target.value); setPage(1); }} className="w-full h-9 rounded-lg border border-input bg-transparent px-3 py-1 text-sm outline-none">
            <option value="All">All Districts</option>
            {districts.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div className="space-y-1.5 flex-1 min-w-[150px]">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Main Category</label>
          <select value={mainCat} onChange={(e) => { setMainCat(e.target.value); setSubCat("All"); setPage(1); }} className="w-full h-9 rounded-lg border border-input bg-transparent px-3 py-1 text-sm outline-none">
            {Object.keys(SUBCATEGORIES).map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="space-y-1.5 flex-1 min-w-[150px]">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Subcategory</label>
          <select value={subCat} onChange={(e) => { setSubCat(e.target.value); setPage(1); }} className="w-full h-9 rounded-lg border border-input bg-transparent px-3 py-1 text-sm outline-none">
            <option value="All">All Subcategories</option>
            {subCategoriesList.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 shrink-0">
        {/* Stats Panel */}
        <div className="bg-card rounded-xl p-4 ring-1 ring-border shadow-sm flex flex-col justify-center">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold flex items-center gap-2"><Database className="size-4" /> Category Stats</h3>
            <Button size="sm" variant="outline" onClick={handleFetchAvailable} disabled={fetchingStats}>
              {fetchingStats ? <RefreshCw className="size-3.5 mr-2 animate-spin" /> : <Search className="size-3.5 mr-2" />}
              Fetch Available
            </Button>
          </div>
          <div className="grid grid-cols-3 gap-2 mt-2">
            <div className="bg-muted/50 p-3 rounded-lg text-center">
              <div className="text-xs text-muted-foreground">Total Scraped</div>
              <div className="text-lg font-bold text-emerald-500">{totalScraped}</div>
            </div>
            <div className="bg-muted/50 p-3 rounded-lg text-center">
              <div className="text-xs text-muted-foreground">Total Available</div>
              <div className="text-lg font-bold">{totalAvailable === null ? "-" : totalAvailable}</div>
            </div>
            <div className="bg-muted/50 p-3 rounded-lg text-center">
              <div className="text-xs text-muted-foreground">Pending</div>
              <div className="text-lg font-bold text-amber-500">{totalAvailable === null ? "-" : Math.max(0, totalAvailable - totalScraped)}</div>
            </div>
          </div>
          {totalAvailable !== null && (
            <div className="mt-2 text-center text-xs text-muted-foreground">
              Estimated <strong>{Math.ceil(totalAvailable / 10)}</strong> pages on JustDial
            </div>
          )}
        </div>

        {/* Target Scrape Panel */}
        <div className="bg-card rounded-xl p-4 ring-1 ring-border shadow-sm flex flex-col justify-center">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold flex items-center gap-2"><Target className="size-4" /> Target Specific Page</h3>
          </div>
          <p className="text-xs text-muted-foreground mb-4">Choose a specific page number to scrape for the selected category and district. This will bypass the full bulk scrape.</p>
          <div className="flex items-end gap-3">
             <div className="space-y-1.5 w-36">
               <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Engine</label>
               <select value={engine} onChange={(e) => setEngine(e.target.value)} className="w-full h-9 rounded-lg border border-input bg-transparent px-3 py-1 text-sm outline-none">
                 <option value="api">⚡ API (Fast)</option>
                 <option value="selenium">Chrome Driver</option>
                 <option value="playwright">Playwright</option>
               </select>
             </div>
             <div className="space-y-1.5 flex-1">
               <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Target Page Number</label>
               <input type="number" min={1} value={targetPage} onChange={(e) => setTargetPage(parseInt(e.target.value) || 1)} className="w-full h-9 rounded-lg border border-input bg-transparent px-3 py-1 text-sm outline-none" />
             </div>
             <Button onClick={handlePreviewPage} disabled={previewing || scraping} variant="outline" className="h-9">
               {previewing ? "Fetching..." : "Preview Page"}
             </Button>
             <Button onClick={handleTargetScrape} disabled={scraping || previewing} className="bg-brand text-white shadow-brand h-9" style={{ background: "var(--gradient-brand)" }}>
               {scraping ? "Scraping..." : "Scrape Target Page"}
             </Button>
          </div>
          
          <div className="mt-3 text-xs flex items-center gap-1.5 bg-muted/30 p-2 rounded border border-border/50">
             <span className="text-muted-foreground shrink-0">URL:</span>
             <a 
               href={`https://www.justdial.com/${district === "All" ? state : district.replace(/\s+/g, "-")}/${subCat === "All" ? mainCat.replace(/\s+/g, "-") : subCat.replace(/\s+/g, "-")}${targetPage > 1 ? `/page-${targetPage}` : ""}`}
               target="_blank" 
               rel="noopener noreferrer"
               className="text-blue-500 hover:underline truncate font-mono"
               title="Open this exact page on JustDial to see what listings will be scraped"
             >
               https://www.justdial.com/{district === "All" ? state : district.replace(/\s+/g, "-")}/{subCat === "All" ? mainCat.replace(/\s+/g, "-") : subCat.replace(/\s+/g, "-")}{targetPage > 1 ? `/page-${targetPage}` : ""}
             </a>
          </div>
        </div>
      </div>

      {/* Data Table */}
      <div className="flex-1 bg-card rounded-xl ring-1 ring-border shadow-sm overflow-hidden flex flex-col min-h-[300px]">
        <div className="p-3 border-b border-border flex justify-between items-center bg-muted/20">
          <h3 className="text-xs font-semibold">Local Database View</h3>
          <div className="flex items-center gap-3">
            <select value={limit} onChange={(e) => { setLimit(Number(e.target.value)); setPage(1); }} className="text-xs rounded border border-input bg-transparent px-2 py-1 outline-none">
              <option value={10}>10 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
              <option value={500}>500 per page</option>
              <option value={999999}>All</option>
            </select>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Page {page} of {Math.ceil(totalScraped / limit) || 1}</span>
              <Button size="icon" variant="outline" className="size-7" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="size-4" /></Button>
              <Button size="icon" variant="outline" className="size-7" disabled={page >= Math.ceil(totalScraped / limit)} onClick={() => setPage(p => p + 1)}><ChevronRight className="size-4" /></Button>
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-auto p-0">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-muted/50 text-xs text-muted-foreground uppercase tracking-wider sticky top-0">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Phone</th>
                <th className="px-4 py-2 font-medium">Category</th>
                <th className="px-4 py-2 font-medium">District</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">No data found for this filter.</td></tr>
              ) : (
                data.map(item => (
                  <tr key={item.id} className="hover:bg-muted/30">
                    <td className="px-4 py-2">{item.name}</td>
                    <td className="px-4 py-2">{item.phone}</td>
                    <td className="px-4 py-2">{item.category}</td>
                    <td className="px-4 py-2">{item.district}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={previewData !== null} onOpenChange={(open) => !open && setPreviewData(null)}>
        <DialogContent className="max-w-md max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Preview: Page {targetPage}</DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto mt-4 space-y-2">
            {previewData?.length === 0 ? (
              <p className="text-center text-sm text-muted-foreground py-8">No listings found on this page.</p>
            ) : (
              previewData?.map((item, idx) => (
                <div key={idx} className="bg-muted/30 p-3 rounded-lg border border-border/50">
                  <div className="font-semibold text-sm">{item.name}</div>
                  <div className="text-xs text-muted-foreground font-mono mt-1">{item.phone || "No phone"}</div>
                </div>
              ))
            )}
          </div>
          <div className="pt-4 flex justify-end">
            <Button onClick={() => setPreviewData(null)} variant="outline">Close</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
