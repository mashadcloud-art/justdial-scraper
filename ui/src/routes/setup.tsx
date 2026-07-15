import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import {
  Zap, User, Lock, Database, Server, CheckCircle,
  ChevronRight, ChevronLeft, Eye, EyeOff, Loader2
} from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/setup")({
  component: SetupWizard,
});

const API = "/api/v1/setup";

type Step = "account" | "backend" | "database" | "done";

export default function SetupWizard() {
  const navigate = useNavigate();
  const [step, setStep]       = useState<Step>("account");
  const [loading, setLoading] = useState(false);

  // Account
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);

  // Backend
  const [backendType, setBackendType] = useState<"local" | "remote">("local");
  const [backendUrl, setBackendUrl]   = useState("http://localhost:8000");

  // Database — pre-filled from existing config
  const MASHAD_DB_URL     = "postgresql://postgres.qdsjbfhjzyypfyryjqxp:HEERnuh%402025@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres";
  const MASHAD_SUP_URL    = "https://qdsjbfhjzyypfyryjqxp.supabase.co";
  const MASHAD_SUP_KEY    = "";

  const [dbType, setDbType]         = useState<"sqlite" | "supabase" | "postgresql">("sqlite");
  const [dbUrl, setDbUrl]           = useState("");
  const [supabaseUrl, setSupabaseUrl]   = useState("");
  const [supabaseKey, setSupabaseKey]   = useState("");
  const [dbTested, setDbTested]     = useState(false);
  const [dbTestMsg, setDbTestMsg]   = useState("");

  const isMashad = username.trim().toLowerCase() === "mashad";

  // When username becomes "mashad", auto-fill DB fields
  function handleUsernameChange(val: string) {
    setUsername(val);
    if (val.trim().toLowerCase() === "mashad") {
      setPassword("mashad");
      setBackendType("local");
      setDbType("supabase");
      setDbUrl(MASHAD_DB_URL);
      setSupabaseUrl(MASHAD_SUP_URL);
      setSupabaseKey(MASHAD_SUP_KEY);
      setDbTested(true);
    }
  }

  // One-click finish for mashad — skip straight to done
  async function handleMashadQuickSetup() {
    setLoading(true);
    try {
      await fetch(`${API}/skip`, { method: "POST" });
      localStorage.setItem("local_user", JSON.stringify({
        name: "Mashad",
        email: "mashad@local",
        avatar: "",
        role: "superadmin",
      }));
      setStep("done");
    } catch {
      toast.error("Failed to complete setup");
    }
    setLoading(false);
  }

  const steps: Step[] = ["account", "backend", "database", "done"];
  const stepIndex = steps.indexOf(step);

  async function testDb() {
    setLoading(true);
    setDbTested(false);
    try {
      const res = await fetch(`${API}/test-db`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ db_type: dbType, db_url: dbUrl, supabase_url: supabaseUrl, supabase_anon_key: supabaseKey }),
      });
      const data = await res.json();
      if (data.status === "ok") {
        setDbTested(true);
        setDbTestMsg(data.message);
        toast.success(data.message);
      } else {
        setDbTestMsg(data.message);
        toast.error(data.message);
      }
    } catch { toast.error("Connection test failed"); }
    setLoading(false);
  }

  async function finishSetup() {
    setLoading(true);
    try {
      const res = await fetch(`${API}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username, password,
          backend_type: backendType,
          backend_url: backendType === "local" ? "http://localhost:8000" : backendUrl,
          db_type: dbType,
          db_url: dbType === "postgresql" ? dbUrl : dbType === "supabase" ? dbUrl : null,
          supabase_url: supabaseUrl || null,
          supabase_anon_key: supabaseKey || null,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        // Auto-login
        localStorage.setItem("local_user", JSON.stringify({
          name: username.charAt(0).toUpperCase() + username.slice(1),
          email: `${username}@local`,
          avatar: "",
          role: "admin",
        }));
        setStep("done");
      } else {
        toast.error(data.detail || "Setup failed");
      }
    } catch { toast.error("Setup failed — backend not responding"); }
    setLoading(false);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-[-20%] left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-brand/10 blur-[120px]" />
      </div>

      <div className="w-full max-w-lg px-4 z-10">
        {/* Logo */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center size-14 rounded-2xl bg-brand/10 ring-1 ring-brand/20 mb-3">
            <Zap className="size-7 text-brand" />
          </div>
          <h1 className="text-2xl font-bold">Welcome to Scapre Pro</h1>
          <p className="text-sm text-muted-foreground mt-1">One-time setup — takes 2 minutes</p>
        </div>

        {/* Progress */}
        {step !== "done" && (
          <div className="flex items-center gap-2 mb-6">
            {["account", "backend", "database"].map((s, i) => (
              <div key={s} className="flex items-center gap-2 flex-1">
                <div className={`size-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                  stepIndex > i ? "bg-brand text-white" :
                  stepIndex === i ? "bg-brand/20 text-brand ring-1 ring-brand" :
                  "bg-muted text-muted-foreground"
                }`}>
                  {stepIndex > i ? <CheckCircle className="size-4" /> : i + 1}
                </div>
                <span className={`text-xs font-medium capitalize ${stepIndex >= i ? "text-foreground" : "text-muted-foreground"}`}>
                  {s}
                </span>
                {i < 2 && <div className={`flex-1 h-px ${stepIndex > i ? "bg-brand" : "bg-border"}`} />}
              </div>
            ))}
          </div>
        )}

        <div className="bg-card rounded-2xl ring-1 ring-border shadow-xl p-6">

          {/* ── STEP 1: ACCOUNT ── */}
          {step === "account" && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <User className="size-5 text-brand" />
                <h2 className="text-base font-semibold">Create your account</h2>
              </div>
              <p className="text-xs text-muted-foreground">This is your personal login for this tool. No signup required.</p>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Username</label>
                <input
                  value={username} onChange={e => handleUsernameChange(e.target.value)}
                  placeholder="e.g. mashad"
                  className="w-full h-11 px-3 rounded-xl ring-1 ring-border bg-background text-sm outline-none focus:ring-brand"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Password</label>
                <div className="relative">
                  <input
                    type={showPass ? "text" : "password"}
                    value={password} onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full h-11 px-3 pr-10 rounded-xl ring-1 ring-border bg-background text-sm outline-none focus:ring-brand"
                  />
                  <button type="button" onClick={() => setShowPass(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    {showPass ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>

              {isMashad && (
                <div className="rounded-xl bg-brand/10 ring-1 ring-brand/30 p-3 text-xs text-brand flex items-center gap-2">
                  <Zap className="size-4 shrink-0" />
                  <span>Superadmin detected — credentials pre-filled from existing config.</span>
                </div>
              )}

              {isMashad ? (
                <Button
                  onClick={handleMashadQuickSetup}
                  disabled={loading}
                  className="w-full h-11 text-white" style={{ background: "var(--gradient-brand)" }}
                >
                  {loading ? <><Loader2 className="size-4 animate-spin mr-2" />Setting up...</> : <>⚡ Quick Setup — Finish Now</>}
                </Button>
              ) : (
                <Button
                  onClick={() => { if (!username || !password) { toast.error("Fill in both fields"); return; } setStep("backend"); }}
                  className="w-full h-11 text-white" style={{ background: "var(--gradient-brand)" }}
                >
                  Next <ChevronRight className="size-4 ml-1" />
                </Button>
              )}
            </div>
          )}

          {/* ── STEP 2: BACKEND ── */}
          {step === "backend" && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <Server className="size-5 text-brand" />
                <h2 className="text-base font-semibold">Choose your backend</h2>
              </div>
              <p className="text-xs text-muted-foreground">The backend runs the scraping engine and API.</p>

              <div className="space-y-2">
                <button onClick={() => setBackendType("local")}
                  className={`w-full p-4 rounded-xl ring-1 text-left transition-all ${backendType === "local" ? "ring-brand bg-brand/5" : "ring-border hover:ring-brand/50"}`}>
                  <div className="font-semibold text-sm">💻 Local (Recommended)</div>
                  <div className="text-xs text-muted-foreground mt-1">Backend runs on this PC. No internet needed for scraping.</div>
                </button>
                <button onClick={() => setBackendType("remote")}
                  className={`w-full p-4 rounded-xl ring-1 text-left transition-all ${backendType === "remote" ? "ring-brand bg-brand/5" : "ring-border hover:ring-brand/50"}`}>
                  <div className="font-semibold text-sm">🌐 Remote Server</div>
                  <div className="text-xs text-muted-foreground mt-1">Connect to your own server URL.</div>
                </button>
              </div>

              {backendType === "remote" && (
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Server URL</label>
                  <input
                    value={backendUrl} onChange={e => setBackendUrl(e.target.value)}
                    placeholder="https://scrapper.yourserver.com"
                    className="w-full h-11 px-3 rounded-xl ring-1 ring-border bg-background text-sm outline-none focus:ring-brand"
                  />
                </div>
              )}

              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setStep("account")} className="flex-1 h-11">
                  <ChevronLeft className="size-4 mr-1" /> Back
                </Button>
                <Button onClick={() => setStep("database")} className="flex-1 h-11 text-white" style={{ background: "var(--gradient-brand)" }}>
                  Next <ChevronRight className="size-4 ml-1" />
                </Button>
              </div>
            </div>
          )}

          {/* ── STEP 3: DATABASE ── */}
          {step === "database" && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <Database className="size-5 text-brand" />
                <h2 className="text-base font-semibold">Choose your database</h2>
              </div>
              <p className="text-xs text-muted-foreground">Where your scraped business data will be stored.</p>

              <div className="space-y-2">
                {[
                  { type: "sqlite",     label: "💾 Local SQLite",  desc: "Data saved on this PC. Zero setup. Best for single user." },
                  { type: "supabase",   label: "☁️ Supabase",      desc: "Free cloud PostgreSQL. Access from anywhere." },
                  { type: "postgresql", label: "🐘 PostgreSQL",    desc: "Your own PostgreSQL server." },
                ].map(opt => (
                  <button key={opt.type} onClick={() => { setDbType(opt.type as any); setDbTested(false); }}
                    className={`w-full p-4 rounded-xl ring-1 text-left transition-all ${dbType === opt.type ? "ring-brand bg-brand/5" : "ring-border hover:ring-brand/50"}`}>
                    <div className="font-semibold text-sm">{opt.label}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{opt.desc}</div>
                  </button>
                ))}
              </div>

              {dbType === "supabase" && (
                <div className="space-y-3">
                  <input value={supabaseUrl} onChange={e => { setSupabaseUrl(e.target.value); setDbTested(false); }}
                    placeholder="https://xxxx.supabase.co"
                    className="w-full h-11 px-3 rounded-xl ring-1 ring-border bg-background text-sm outline-none focus:ring-brand" />
                  <input value={supabaseKey} onChange={e => { setSupabaseKey(e.target.value); setDbTested(false); }}
                    placeholder="anon public key"
                    className="w-full h-11 px-3 rounded-xl ring-1 ring-border bg-background text-sm outline-none focus:ring-brand" />
                  <input value={dbUrl} onChange={e => { setDbUrl(e.target.value); setDbTested(false); }}
                    placeholder="postgresql://postgres:pass@db.xxxx.supabase.co:5432/postgres"
                    className="w-full h-11 px-3 rounded-xl ring-1 ring-border bg-background text-sm outline-none focus:ring-brand" />
                </div>
              )}

              {dbType === "postgresql" && (
                <input value={dbUrl} onChange={e => { setDbUrl(e.target.value); setDbTested(false); }}
                  placeholder="postgresql://user:pass@host:5432/dbname"
                  className="w-full h-11 px-3 rounded-xl ring-1 ring-border bg-background text-sm outline-none focus:ring-brand" />
              )}

              {dbType !== "sqlite" && (
                <button onClick={testDb} disabled={loading}
                  className={`w-full h-10 rounded-xl text-sm font-medium ring-1 transition-all flex items-center justify-center gap-2 ${
                    dbTested ? "ring-emerald-500 bg-emerald-500/10 text-emerald-400" : "ring-border hover:ring-brand/50"
                  }`}>
                  {loading ? <Loader2 className="size-4 animate-spin" /> : dbTested ? <CheckCircle className="size-4" /> : null}
                  {loading ? "Testing..." : dbTested ? "Connected ✓" : "Test Connection"}
                </button>
              )}
              {dbTestMsg && !dbTested && <p className="text-xs text-red-400">{dbTestMsg}</p>}

              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setStep("backend")} className="flex-1 h-11">
                  <ChevronLeft className="size-4 mr-1" /> Back
                </Button>
                <Button
                  onClick={finishSetup}
                  disabled={loading || (dbType !== "sqlite" && !dbTested)}
                  className="flex-1 h-11 text-white"
                  style={{ background: "var(--gradient-brand)" }}
                >
                  {loading ? <Loader2 className="size-4 animate-spin mr-2" /> : null}
                  Finish Setup
                </Button>
              </div>
            </div>
          )}

          {/* ── DONE ── */}
          {step === "done" && (
            <div className="text-center space-y-4 py-4">
              <div className="inline-flex items-center justify-center size-16 rounded-full bg-emerald-500/10 ring-1 ring-emerald-500/30">
                <CheckCircle className="size-8 text-emerald-400" />
              </div>
              <div>
                <h2 className="text-lg font-bold">You're all set!</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Account created. Backend and database configured.
                </p>
              </div>
              <div className="rounded-xl bg-muted/30 ring-1 ring-border p-4 text-left space-y-1.5 text-xs">
                <p>👤 Username: <span className="font-mono text-foreground">{username}</span></p>
                <p>🖥️ Backend: <span className="font-mono text-foreground">{backendType === "local" ? "Local (this PC)" : backendUrl}</span></p>
                <p>🗄️ Database: <span className="font-mono text-foreground capitalize">{dbType}</span></p>
              </div>
              <Button
                onClick={() => navigate({ to: "/" })}
                className="w-full h-11 text-white"
                style={{ background: "var(--gradient-brand)" }}
              >
                Open Scapre Pro →
              </Button>
            </div>
          )}
        </div>

        <p className="text-center text-[10px] text-muted-foreground mt-4">
          Scapre Pro v3.0 · You can change these settings later in Settings
        </p>
        <p className="text-center text-xs text-muted-foreground mt-2">
          Already set up?{" "}
          <button
            onClick={async () => {
              await fetch(`${API}/skip`, { method: "POST" }).catch(() => {});
              navigate({ to: "/login" });
            }}
            className="text-brand hover:underline font-medium"
          >
            Go to Login →
          </button>
        </p>
      </div>
    </div>
  );
}
