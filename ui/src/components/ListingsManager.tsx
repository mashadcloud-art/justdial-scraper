import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Database, Search, Target, RefreshCw, ChevronLeft, ChevronRight, Image as ImageIcon, Play, Square, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

// Make sure to pass CITIES and SUBCATEGORIES from index.tsx or import them if exported
export default function ListingsManager({
  API,
  CITIES,
  SUBCATEGORIES,
  states,
  initialState,
  initialDistrict,
  initialCategory,
  initialTodayOnly = false,
}: {
  API: string;
  CITIES: Record<string, string[]>;
  SUBCATEGORIES: Record<string, string[]>;
  states: string[];
  initialState?: string;
  initialDistrict?: string;
  initialCategory?: string;
  initialTodayOnly?: boolean;
}) {
  const [state, setState] = useState(initialState || "All");
  const [district, setDistrict] = useState(initialDistrict || "All");
  const [mainCat, setMainCat] = useState("All");
  const [subCat, setSubCat] = useState(initialCategory || "All");
  const [source, setSource] = useState("All");
  const [searchQuery, setSearchQuery] = useState("");
  const [todayOnly, setTodayOnly] = useState(initialTodayOnly);

  // Sync props when they change (e.g. from parent modal clicks)
  useEffect(() => {
    if (initialState) setState(initialState);
  }, [initialState]);

  useEffect(() => {
    if (initialDistrict) setDistrict(initialDistrict);
  }, [initialDistrict]);

  useEffect(() => {
    if (initialCategory) setSubCat(initialCategory);
  }, [initialCategory]);

  useEffect(() => {
    if (initialTodayOnly !== undefined) setTodayOnly(initialTodayOnly);
  }, [initialTodayOnly]);

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
  
  // For single-image scraping
  const [singleImageScraping, setSingleImageScraping] = useState(false);
  const [maxImagesPerPlace, setMaxImagesPerPlace] = useState(20);
  const [singleImageLogs, setSingleImageLogs] = useState<{time: string; ok: boolean; msg: string}[]>([]);
  const singleImageLogRef = useRef<HTMLDivElement>(null);
  const [showLogs, setShowLogs] = useState(false);

  const districts = CITIES[state] || [];
  const subCategoriesList = SUBCATEGORIES[mainCat] || [];

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPage();
    }, 300);
    return () => clearTimeout(timer);
  }, [page, district, state, subCat, searchQuery, limit, source, todayOnly]);

  async function fetchPage() {
    try {
      const qs = new URLSearchParams({ page: page.toString(), limit: limit.toString() });
      if (state && state !== "All") qs.append("state", state);
      if (district && district !== "All") qs.append("district", district);
      if (subCat && subCat !== "All") qs.append("category", subCat);
      if (source && source !== "All") qs.append("source", source);
      if (searchQuery) qs.append("search", searchQuery);
      if (todayOnly) qs.append("today_only", "true");

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

  async function startSingleImageScrape() {
    if (singleImageScraping) return;
    setSingleImageScraping(true);
    setSingleImageLogs([]);
    setShowLogs(true);

    function addLog(ok: boolean, msg: string) {
      setSingleImageLogs(logs => [
        ...logs,
        { time: new Date().toLocaleTimeString("en-GB", { hour12: false }), ok, msg }
      ]);
    }

    addLog(true, "Starting single-image listings scrape...");

    try {
      const res = await fetch(`${API}/gmaps/scrape-single-image-listings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          district: district === "All" ? undefined : district,
          category: subCat === "All" ? mainCat : subCat,
          max_images_per_place: maxImagesPerPlace
        }),
      });

      if (!res.ok) {
        const err = await res.text();
        addLog(false, `Failed to start: ${err}`);
        setSingleImageScraping(false);
        return;
      }

      addLog(true, "Scrape started, polling for updates...");

      // Poll for status and logs
      let lastIdx = 0;
      const poll = setInterval(async () => {
        try {
          const sr = await fetch(`${API}/gmaps/status?last_idx=${lastIdx}`);
          if (!sr.ok) return;
          const data = await sr.json();
          
          if (data.logs?.length) {
            data.logs.forEach((log: any) => {
              addLog(log.ok ?? true, log.msg ?? log.message ?? JSON.stringify(log));
            });
            lastIdx = data.next_idx ?? lastIdx + data.logs.length;
          }
          
          if (!data.running) {
            clearInterval(poll);
            setSingleImageScraping(false);
            addLog(true, "Scrape complete!");
            fetchPage();
          }
        } catch {
          // Ignore polling errors
        }
      }, 2000);

    } catch (e: any) {
      addLog(false, `Error: ${e.message}`);
      setSingleImageScraping(false);
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
            <option value="All">All States</option>
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
        <div className="space-y-1.5 flex-1 min-w-[150px]">
          <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Source</label>
          <select value={source} onChange={(e) => { setSource(e.target.value); setPage(1); }} className="w-full h-9 rounded-lg border border-input bg-transparent px-3 py-1 text-sm outline-none">
            <option value="All">All Sources</option>
            <option value="justdial">JustDial</option>
            <option value="google">Google Maps</option>
          </select>
        </div>
        <div className="flex items-center gap-2 h-9 pb-1 shrink-0">
          <input
            type="checkbox"
            id="todayOnlyCheck"
            checked={todayOnly}
            onChange={(e) => { setTodayOnly(e.target.checked); setPage(1); }}
            className="rounded border-input text-brand focus:ring-brand size-4 cursor-pointer"
          />
          <label htmlFor="todayOnlyCheck" className="text-xs font-semibold text-foreground/80 cursor-pointer select-none">
            Scraped Today Only
          </label>
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
      
      {/* Single-Image Scrape Panel */}
      <div className="bg-card rounded-xl p-4 ring-1 ring-border shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <ImageIcon className="size-4 text-brand" />
            Scrape Missing Images from Google Maps
          </h3>
          {showLogs && (
            <Button size="sm" variant="outline" onClick={() => setShowLogs(false)}>
              Hide Logs
            </Button>
          )}
        </div>
        <p className="text-xs text-muted-foreground mb-4">
          Finds all listings that only have 1 image and scrapes more high-res images from Google Maps (saves links only, no downloads).
        </p>
        <div className="flex items-end gap-3">
          <div className="space-y-1.5 w-48">
            <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Max Images per Place</label>
            <input
              type="number"
              min="1"
              max="100"
              value={maxImagesPerPlace}
              onChange={(e) => setMaxImagesPerPlace(Math.max(1, Math.min(100, parseInt(e.target.value) || 20)))}
              className="w-full h-9 rounded-lg border border-input bg-transparent px-3 py-1 text-sm outline-none"
            />
          </div>
          <div className="space-y-1.5 flex-1">
            <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Selected Filters</label>
            <div className="text-xs text-muted-foreground">
              {district === "All" ? "All Districts" : district} / {subCat === "All" ? mainCat : subCat}
            </div>
          </div>
          <Button
            onClick={startSingleImageScrape}
            disabled={singleImageScraping}
            className="h-16 text-white text-lg font-bold shadow-2xl animate-pulse"
            style={{ background: "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)" }}
          >
            <Play className="size-5 mr-2" />
            {singleImageScraping ? "SCRAPING NOW..." : "🟢 CLICK HERE TO SCRAPE MISSING IMAGES 🟢"}
          </Button>
        </div>
        
        {showLogs && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold flex items-center gap-1">
                <Activity className="size-3" /> Activity Log
              </h4>
              <button
                onClick={() => setSingleImageLogs([])}
                className="text-[10px] text-muted-foreground hover:text-destructive transition-colors"
              >
                Clear
              </button>
            </div>
            <div
              ref={singleImageLogRef}
              className="h-32 overflow-y-auto font-mono text-xs space-y-0.5 bg-muted/20 rounded-lg p-3 border border-border"
            >
              {singleImageLogs.length === 0 ? (
                <p className="text-muted-foreground text-center py-4">Logs will appear here when scraping starts...</p>
              ) : (
                singleImageLogs.map((log, i) => (
                  <div key={i} className="flex gap-2 leading-5">
                    <span className="text-muted-foreground shrink-0">[{log.time}]</span>
                    <span className={log.ok ? "text-emerald-400" : "text-red-400"}>{log.ok ? "✓" : "✗"}</span>
                    <span className="text-foreground/80 break-all">{log.msg}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
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
                <th className="px-4 py-2 font-medium">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No data found for this filter.</td></tr>
              ) : (
                data.map(item => (
                  <tr key={item.id} className="hover:bg-muted/30">
                    <td className="px-4 py-2">{item.name}</td>
                    <td className="px-4 py-2">{item.phone}</td>
                    <td className="px-4 py-2">{item.category}</td>
                    <td className="px-4 py-2">{item.district}</td>
                    <td className="px-4 py-2">
                      {item.jd_url ? (
                        <a 
                          href={item.jd_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className={cn(
                            "px-1.5 py-0.5 rounded text-[10px] font-bold border transition-colors inline-block hover:underline",
                            item.jd_url.includes("google.com/maps") 
                              ? "bg-blue-500/10 text-blue-500 border-blue-500/20 hover:bg-blue-500/20" 
                              : "bg-orange-500/10 text-orange-500 border-orange-500/20 hover:bg-orange-500/20"
                          )}
                        >
                          {item.jd_url.includes("google.com/maps") ? "Google Maps ↗" : "JustDial ↗"}
                        </a>
                      ) : (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-muted text-muted-foreground border border-border">Other</span>
                      )}
                    </td>
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
