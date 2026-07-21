import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  Activity, ExternalLink, Image as ImageIcon, Pause, Play, RefreshCw,
  Square, Stethoscope, User,
} from "lucide-react";
import { cn } from "@/lib/utils";

type JobStatus = "pending" | "seeding" | "running" | "paused" | "stopped" | "completed" | "failed";

type Job = {
  job_id: string;
  status: JobStatus;
  control: string;
  district_filter: string | null;
  category_keywords: string | null;
  include_partial: boolean;
  max_listings: number | null;
  total_listings: number;
  processed: number;
  succeeded: number;
  partial: number;
  failed: number;
  log_tail?: { time: string; msg: string }[];
};

type Stats = {
  total_profiles: number;
  by_overall_status: Record<string, number>;
  total_doctors: number;
  doctors_with_photo: number;
  total_gallery_images: number;
};

type ResultRow = {
  listing_id: number;
  listing_name: string | null;
  listing_district: string | null;
  website_url: string | null;
  website_status: string | null;
  gallery_image_count: number;
  doctors_page_url: string | null;
  doctor_count: number;
  overall_status: string;
  error_detail: string | null;
};

type Doctor = {
  id: number;
  name: string | null;
  photo_url: string | null;
  photo_status: string | null;
  specialty: string | null;
  qualifications: string | null;
  experience: string | null;
  phone: string | null;
  email: string | null;
  source_url: string | null;
};

type ListingDetail = ResultRow & {
  gallery_images: string[];
  doctors: Doctor[];
};

const ACTIVE_STATUSES = new Set(["pending", "seeding", "running", "paused"]);

function statusColor(status: string) {
  switch (status) {
    case "completed": return "bg-emerald-500/10 text-emerald-600";
    case "completed_partial": return "bg-amber-500/10 text-amber-600";
    case "failed": return "bg-destructive/10 text-destructive";
    case "in_progress":
    case "running": return "bg-brand/10 text-brand";
    case "paused": return "bg-amber-500/10 text-amber-600";
    default: return "bg-muted text-muted-foreground";
  }
}

export default function HospitalsPanel({ API }: { API: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [starting, setStarting] = useState(false);
  const [controlPending, setControlPending] = useState(false);

  const [district, setDistrict] = useState("");
  const [keywords, setKeywords] = useState("hospital");
  const [includePartial, setIncludePartial] = useState(false);
  const [maxListings, setMaxListings] = useState("");

  const [stats, setStats] = useState<Stats | null>(null);

  const [resultStatus, setResultStatus] = useState("");
  const [results, setResults] = useState<ResultRow[]>([]);
  const [resultsTotal, setResultsTotal] = useState(0);
  const [resultsPage, setResultsPage] = useState(1);
  const resultsLimit = 20;

  const [detail, setDetail] = useState<ListingDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const logRef = useRef<HTMLDivElement>(null);
  const isActive = !!job && ACTIVE_STATUSES.has(job.status);

  async function fetchLatestJob() {
    try {
      const res = await fetch(`${API}/hospital_enrichment/jobs?limit=1`);
      if (!res.ok) return;
      const data = await res.json();
      const latest = data.jobs?.[0];
      if (!latest) { setJob(null); return; }
      const detailRes = await fetch(`${API}/hospital_enrichment/jobs/${latest.job_id}`);
      if (detailRes.ok) setJob(await detailRes.json());
    } catch { /* keep last known job */ }
  }

  async function fetchStats() {
    try {
      const res = await fetch(`${API}/hospital_enrichment/stats`);
      if (res.ok) setStats(await res.json());
    } catch { /* ignore */ }
  }

  async function fetchResults() {
    try {
      const params = new URLSearchParams({
        limit: String(resultsLimit),
        offset: String((resultsPage - 1) * resultsLimit),
      });
      if (resultStatus) params.set("status", resultStatus);
      const res = await fetch(`${API}/hospital_enrichment/results?${params}`);
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
        setResultsTotal(data.total || 0);
      }
    } catch { /* ignore */ }
  }

  useEffect(() => {
    fetchLatestJob();
    fetchStats();
    const jobInterval = setInterval(fetchLatestJob, 3000);
    const statsInterval = setInterval(fetchStats, 8000);
    return () => { clearInterval(jobInterval); clearInterval(statsInterval); };
  }, []);

  useEffect(() => { fetchResults(); }, [resultStatus, resultsPage]);

  // Refresh results + stats whenever the job finishes a listing or completes.
  useEffect(() => {
    if (job && (job.status === "completed" || job.status === "stopped" || job.status === "failed")) {
      fetchResults();
      fetchStats();
    }
  }, [job?.status, job?.processed]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [job?.log_tail]);

  async function startJob() {
    setStarting(true);
    try {
      const res = await fetch(`${API}/hospital_enrichment/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          district: district.trim() || null,
          category_keywords: keywords.split(",").map(k => k.trim()).filter(Boolean),
          include_partial: includePartial,
          max_listings: maxListings.trim() ? Number(maxListings) : null,
        }),
      });
      if (res.ok) {
        toast.success("Hospital enrichment job started.");
        await fetchLatestJob();
      } else {
        const err = await res.json().catch(() => null);
        toast.error(err?.detail || "Failed to start job.");
      }
    } catch {
      toast.error("Failed to reach server.");
    }
    setStarting(false);
  }

  async function sendControl(action: "pause" | "resume" | "stop") {
    if (!job) return;
    setControlPending(true);
    try {
      const res = await fetch(`${API}/hospital_enrichment/jobs/${job.job_id}/${action}`, { method: "POST" });
      if (res.ok) {
        toast.success(`Job ${action === "resume" ? "resumed" : action + "d"}.`);
        await fetchLatestJob();
      } else {
        toast.error(`Failed to ${action} job.`);
      }
    } catch {
      toast.error("Failed to reach server.");
    }
    setControlPending(false);
  }

  async function openDetail(listingId: number) {
    setDetailLoading(true);
    setDetail(null);
    try {
      const res = await fetch(`${API}/hospital_enrichment/listings/${listingId}`);
      if (res.ok) setDetail(await res.json());
      else toast.error("No enrichment data for this listing yet.");
    } catch {
      toast.error("Failed to reach server.");
    }
    setDetailLoading(false);
  }

  const progressPct = job && job.total_listings > 0
    ? Math.min(100, Math.round((job.processed / job.total_listings) * 100))
    : 0;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Job control */}
        <section className="p-6 rounded-2xl ring-1 ring-brand/30 bg-card shadow-elegant space-y-4">
          <div className="flex items-center gap-2">
            <Stethoscope className="size-4 text-brand" />
            <h3 className="text-base font-semibold">Hospital Enrichment</h3>
            {job && (
              <span className={cn("ml-auto text-[9px] px-2 py-0.5 rounded-full font-bold uppercase tracking-widest", statusColor(job.status))}>
                {job.status}
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Finds each hospital listing's official website, then crawls it for a photo gallery and a doctors/team page.
          </p>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">District (optional)</label>
              <input
                type="text"
                value={district}
                onChange={e => setDistrict(e.target.value)}
                placeholder="e.g. Ernakulam"
                disabled={isActive}
                className="w-full h-10 rounded-lg px-3 text-sm bg-background ring-1 ring-border outline-none focus:ring-brand disabled:opacity-50"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">Category keywords</label>
              <input
                type="text"
                value={keywords}
                onChange={e => setKeywords(e.target.value)}
                placeholder="hospital, clinic"
                disabled={isActive}
                className="w-full h-10 rounded-lg px-3 text-sm bg-background ring-1 ring-border outline-none focus:ring-brand disabled:opacity-50"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 items-end">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">Max listings (optional)</label>
              <input
                type="number"
                min={1}
                value={maxListings}
                onChange={e => setMaxListings(e.target.value)}
                placeholder="No limit"
                disabled={isActive}
                className="w-full h-10 rounded-lg px-3 text-sm bg-background ring-1 ring-border outline-none focus:ring-brand disabled:opacity-50"
              />
            </div>
            <label className="flex items-center gap-2 h-10 px-3 rounded-lg ring-1 ring-border cursor-pointer">
              <Checkbox checked={includePartial} onCheckedChange={v => setIncludePartial(!!v)} disabled={isActive} />
              <span className="text-xs text-muted-foreground">Re-crawl partial results</span>
            </label>
          </div>

          <div className="flex gap-2">
            {!isActive ? (
              <Button onClick={startJob} disabled={starting} className="flex-1 h-10 text-white text-xs" style={{ background: "var(--gradient-brand)" }}>
                <Play className="size-3.5 mr-1.5" />{starting ? "Starting..." : "Start Enrichment"}
              </Button>
            ) : (
              <>
                {job!.status === "paused" ? (
                  <Button onClick={() => sendControl("resume")} disabled={controlPending} className="flex-1 h-10 text-white text-xs" style={{ background: "var(--gradient-brand)" }}>
                    <Play className="size-3.5 mr-1.5" />Resume
                  </Button>
                ) : (
                  <Button onClick={() => sendControl("pause")} disabled={controlPending} variant="outline" className="flex-1 h-10 text-xs">
                    <Pause className="size-3.5 mr-1.5" />Pause
                  </Button>
                )}
                <Button onClick={() => sendControl("stop")} disabled={controlPending} variant="outline"
                  className="flex-1 h-10 text-xs text-destructive border-destructive/40 hover:bg-destructive/10">
                  <Square className="size-3.5 mr-1.5" />Stop
                </Button>
              </>
            )}
          </div>

          {job && (
            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                <span>{job.processed} / {job.total_listings || "?"} processed</span>
                <span>{progressPct}%</span>
              </div>
              <Progress value={progressPct} />
              <div className="grid grid-cols-3 gap-2 pt-1">
                <div className="rounded-lg ring-1 ring-border bg-background p-2 text-center">
                  <div className="text-[9px] uppercase tracking-widest text-muted-foreground font-bold">Succeeded</div>
                  <div className="text-base font-bold text-emerald-500 mt-0.5">{job.succeeded}</div>
                </div>
                <div className="rounded-lg ring-1 ring-border bg-background p-2 text-center">
                  <div className="text-[9px] uppercase tracking-widest text-muted-foreground font-bold">Partial</div>
                  <div className="text-base font-bold text-amber-500 mt-0.5">{job.partial}</div>
                </div>
                <div className="rounded-lg ring-1 ring-border bg-background p-2 text-center">
                  <div className="text-[9px] uppercase tracking-widest text-muted-foreground font-bold">Failed</div>
                  <div className="text-base font-bold text-destructive mt-0.5">{job.failed}</div>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Live log + overall stats */}
        <section className="p-6 rounded-2xl ring-1 ring-border bg-card shadow-elegant space-y-3 flex flex-col">
          <div className="flex items-center gap-2">
            <Activity className="size-4 text-brand" />
            <h3 className="text-base font-semibold">Live Log</h3>
            {isActive && <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />}
            <span className="ml-auto text-[9px] text-muted-foreground">auto every 3s</span>
          </div>
          <div ref={logRef} className="flex-1 min-h-[180px] max-h-[220px] overflow-y-auto rounded-lg bg-background ring-1 ring-border p-3 font-mono text-[11px] whitespace-pre-wrap leading-relaxed">
            {job?.log_tail?.length ? (
              job.log_tail.map((l, i) => (
                <div key={i}><span className="text-muted-foreground">[{l.time}]</span> {l.msg}</div>
              ))
            ) : "No log output yet."}
          </div>

          {stats && (
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="rounded-lg ring-1 ring-border bg-background p-2.5">
                <div className="text-[9px] uppercase tracking-widest text-muted-foreground font-bold">Total Profiles</div>
                <div className="text-lg font-bold text-brand mt-0.5">{stats.total_profiles}</div>
              </div>
              <div className="rounded-lg ring-1 ring-border bg-background p-2.5">
                <div className="text-[9px] uppercase tracking-widest text-muted-foreground font-bold">Doctors Found</div>
                <div className="text-lg font-bold mt-0.5">{stats.total_doctors} <span className="text-[10px] font-normal text-muted-foreground">({stats.doctors_with_photo} w/ photo)</span></div>
              </div>
              <div className="rounded-lg ring-1 ring-border bg-background p-2.5 col-span-2">
                <div className="text-[9px] uppercase tracking-widest text-muted-foreground font-bold">Gallery Images</div>
                <div className="text-lg font-bold mt-0.5">{stats.total_gallery_images}</div>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Results browser */}
      <section className="p-6 rounded-2xl ring-1 ring-border bg-card shadow-elegant space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <ImageIcon className="size-4 text-brand" />
          <h3 className="text-base font-semibold">Results</h3>
          <span className="text-[10px] text-muted-foreground">{resultsTotal} total</span>
          <select
            value={resultStatus}
            onChange={e => { setResultStatus(e.target.value); setResultsPage(1); }}
            className="ml-auto h-8 rounded-lg px-2 text-xs bg-background ring-1 ring-border outline-none focus:ring-brand"
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
            <option value="completed_partial">Partial</option>
            <option value="failed">Failed</option>
          </select>
          <button onClick={() => fetchResults()} className="text-[10px] text-brand hover:underline px-2 py-1 ring-1 ring-brand/30 rounded-full flex items-center gap-1">
            <RefreshCw className="size-3" />Refresh
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-muted-foreground border-b border-border">
                <th className="py-2 pr-3 font-semibold">Hospital</th>
                <th className="py-2 pr-3 font-semibold">District</th>
                <th className="py-2 pr-3 font-semibold">Website</th>
                <th className="py-2 pr-3 font-semibold">Gallery</th>
                <th className="py-2 pr-3 font-semibold">Doctors</th>
                <th className="py-2 pr-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {results.length === 0 ? (
                <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">No results yet.</td></tr>
              ) : results.map(r => (
                <tr
                  key={r.listing_id}
                  className="border-b border-border/50 hover:bg-accent/40 cursor-pointer transition-colors"
                  onClick={() => openDetail(r.listing_id)}
                >
                  <td className="py-2 pr-3 font-medium">{r.listing_name || `#${r.listing_id}`}</td>
                  <td className="py-2 pr-3 text-muted-foreground">{r.listing_district || "—"}</td>
                  <td className="py-2 pr-3">
                    {r.website_url ? (
                      <a href={r.website_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="text-brand hover:underline flex items-center gap-1">
                        <ExternalLink className="size-3" />Visit
                      </a>
                    ) : <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="py-2 pr-3 text-muted-foreground">{r.gallery_image_count}</td>
                  <td className="py-2 pr-3 text-muted-foreground">{r.doctor_count}</td>
                  <td className="py-2 pr-3">
                    <span className={cn("text-[9px] px-1.5 py-0.5 rounded-full font-bold uppercase tracking-wide", statusColor(r.overall_status))}>
                      {r.overall_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {resultsTotal > resultsLimit && (
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setResultsPage(p => Math.max(1, p - 1))}
              disabled={resultsPage <= 1}
              className="text-xs px-3 py-1.5 rounded-lg ring-1 ring-border disabled:opacity-40 hover:bg-accent"
            >
              Previous
            </button>
            <span className="text-[10px] text-muted-foreground">
              Page {resultsPage} of {Math.max(1, Math.ceil(resultsTotal / resultsLimit))}
            </span>
            <button
              onClick={() => setResultsPage(p => (p * resultsLimit < resultsTotal ? p + 1 : p))}
              disabled={resultsPage * resultsLimit >= resultsTotal}
              className="text-xs px-3 py-1.5 rounded-lg ring-1 ring-border disabled:opacity-40 hover:bg-accent"
            >
              Next
            </button>
          </div>
        )}
      </section>

      {/* Detail dialog */}
      <Dialog open={!!detail || detailLoading} onOpenChange={(open) => { if (!open) { setDetail(null); } }}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Stethoscope className="size-4 text-brand" />
              {detail?.listing_name || "Loading..."}
            </DialogTitle>
          </DialogHeader>

          {detailLoading && !detail ? (
            <div className="py-10 text-center text-sm text-muted-foreground">Loading enrichment details...</div>
          ) : detail && (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className={cn("px-2 py-0.5 rounded-full font-bold uppercase tracking-wide", statusColor(detail.overall_status))}>
                  {detail.overall_status}
                </span>
                {detail.listing_district && <span className="text-muted-foreground">{detail.listing_district}</span>}
                {detail.website_url && (
                  <a href={detail.website_url} target="_blank" rel="noopener noreferrer" className="text-brand hover:underline flex items-center gap-1 ml-auto">
                    <ExternalLink className="size-3.5" />{detail.website_url}
                  </a>
                )}
              </div>
              {detail.error_detail && (
                <p className="text-xs text-destructive bg-destructive/5 ring-1 ring-destructive/20 rounded-lg p-2.5">{detail.error_detail}</p>
              )}

              {/* Gallery */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
                  <ImageIcon className="size-3.5" />Gallery ({detail.gallery_images.length})
                </h4>
                {detail.gallery_images.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No gallery images found.</p>
                ) : (
                  <div className="grid grid-cols-4 gap-2">
                    {detail.gallery_images.map((url, i) => (
                      <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="aspect-square rounded-lg overflow-hidden ring-1 ring-border bg-muted block">
                        <img src={url} alt={`Gallery ${i + 1}`} className="w-full h-full object-cover" loading="lazy" />
                      </a>
                    ))}
                  </div>
                )}
              </div>

              {/* Doctors */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
                  <User className="size-3.5" />Doctors ({detail.doctors.length})
                </h4>
                {detail.doctors.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No doctor profiles found.</p>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    {detail.doctors.map(doc => (
                      <div key={doc.id} className="rounded-xl ring-1 ring-border bg-background p-3 flex gap-3">
                        <div className="size-14 rounded-full overflow-hidden ring-1 ring-border bg-muted shrink-0 flex items-center justify-center">
                          {doc.photo_url ? (
                            <img src={doc.photo_url} alt={doc.name || "Doctor"} className="w-full h-full object-cover" loading="lazy" />
                          ) : (
                            <User className="size-6 text-muted-foreground" />
                          )}
                        </div>
                        <div className="min-w-0 space-y-0.5">
                          <p className="text-xs font-semibold truncate">{doc.name || "Unnamed"}</p>
                          {doc.specialty && <p className="text-[10px] text-brand truncate">{doc.specialty}</p>}
                          {doc.qualifications && <p className="text-[10px] text-muted-foreground truncate">{doc.qualifications}</p>}
                          {doc.experience && <p className="text-[10px] text-muted-foreground truncate">{doc.experience}</p>}
                          {(doc.phone || doc.email) && (
                            <p className="text-[10px] text-muted-foreground truncate">{[doc.phone, doc.email].filter(Boolean).join(" · ")}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
