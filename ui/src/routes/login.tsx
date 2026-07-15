import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Eye, EyeOff, Zap, Lock, User, Chrome, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/login")({
  component: LoginPage,
});

const SUPABASE_URL = "https://qdsjbfhjzyypfyryjqxp.supabase.co";
const REMEMBER_KEY = "scapre_saved_login";

function decodeJwt(token: string) {
  try {
    const seg = token.split(".")[1];
    const pad = seg + "=".repeat((4 - seg.length % 4) % 4);
    return JSON.parse(atob(pad.replace(/-/g, "+").replace(/_/g, "/")));
  } catch { return null; }
}

export default function LoginPage() {
  const navigate  = useNavigate();
  const [tab, setTab]           = useState<"local" | "google" | "guest">("local");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [remember, setRemember] = useState(false);
  const [loading, setLoading]   = useState(false);

  // ── On mount: auto-login if session exists, or fill saved credentials ──
  useEffect(() => {
    // Already logged in → go home
    if (localStorage.getItem("local_user") || localStorage.getItem("sb_access_token")) {
      navigate({ to: "/" });
      return;
    }

    // Supabase OAuth callback
    const hash = window.location.hash;
    if (hash.includes("access_token")) {
      const params = new URLSearchParams(hash.replace("#", "?"));
      const accessToken = params.get("access_token");
      if (accessToken) {
        localStorage.setItem("sb_access_token", accessToken);
        const payload = decodeJwt(accessToken);
        if (payload) {
          localStorage.setItem("local_user", JSON.stringify({
            name: payload.user_metadata?.full_name || payload.email,
            email: payload.email, avatar: payload.user_metadata?.avatar_url || "", role: "user",
          }));
        }
        window.history.replaceState(null, "", "/login");
        navigate({ to: "/" });
        return;
      }
    }

    // Restore saved credentials (Remember me)
    const saved = localStorage.getItem(REMEMBER_KEY);
    if (saved) {
      try {
        const { username: u, password: p } = JSON.parse(saved);
        setUsername(u);
        setPassword(p);
        setRemember(true);
        // Auto-login silently
        _doLogin(u, p, true);
      } catch {
        localStorage.removeItem(REMEMBER_KEY);
      }
    }

    // Check if setup is needed
    fetch("/api/v1/setup/status")
      .then(r => r.json())
      .then(data => {
        if (!data.setup_done || !data.has_users) {
          // Auto-seed mashad account and mark setup done
          fetch("/api/v1/setup/skip", { method: "POST" }).catch(() => {});
        }
      })
      .catch(() => {});
  }, []);

  async function _doLogin(u: string, p: string, silent = false) {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/setup/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p }),
      });
      const data = await res.json();

      if (res.ok && data.status === "ok") {
        // Save credentials if remember me
        if (remember || silent) {
          localStorage.setItem(REMEMBER_KEY, JSON.stringify({ username: u, password: p }));
        } else {
          localStorage.removeItem(REMEMBER_KEY);
        }
        localStorage.setItem("local_user", JSON.stringify({
          name: data.user.name,
          email: `${u}@local`,
          avatar: "",
          role: data.user.role,
        }));
        if (!silent) toast.success(`Welcome, ${data.user.name}!`);
        navigate({ to: "/" });
      } else {
        if (!silent) toast.error(data.detail || "Invalid username or password");
        localStorage.removeItem(REMEMBER_KEY);
      }
    } catch {
      if (!silent) toast.error("Cannot connect to backend. Make sure the app is running.");
    }
    setLoading(false);
  }

  function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !password) { toast.error("Enter username and password"); return; }
    _doLogin(username, password, false);
  }

  function handleGoogleLogin() {
    const redirect = encodeURIComponent(window.location.origin + "/login");
    window.location.href = `${SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to=${redirect}`;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-[-20%] left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-brand/10 blur-[120px]" />
      </div>

      <div className="w-full max-w-sm px-4 z-10">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center size-16 rounded-2xl bg-brand/10 ring-1 ring-brand/20 mb-4">
            <Zap className="size-8 text-brand" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">Scapre Pro</h1>
          <p className="text-sm text-muted-foreground mt-1">Sign in to continue</p>
        </div>

        {/* Tab selector */}
        <div className="flex gap-1 p-1 bg-muted/50 rounded-xl mb-4">
          <button onClick={() => setTab("local")}
            className={`flex-1 h-9 rounded-lg text-xs font-semibold transition-all ${tab === "local" ? "bg-card shadow text-foreground ring-1 ring-border" : "text-muted-foreground hover:text-foreground"}`}>
            Username
          </button>
          <button onClick={() => setTab("google")}
            className={`flex-1 h-9 rounded-lg text-xs font-semibold transition-all ${tab === "google" ? "bg-card shadow text-foreground ring-1 ring-border" : "text-muted-foreground hover:text-foreground"}`}>
            Google
          </button>
          <button onClick={() => setTab("guest")}
            className={`flex-1 h-9 rounded-lg text-xs font-semibold transition-all ${tab === "guest" ? "bg-card shadow text-foreground ring-1 ring-border" : "text-muted-foreground hover:text-foreground"}`}>
            Guest
          </button>
        </div>

        {/* Card */}
        <div className="bg-card rounded-2xl ring-1 ring-border shadow-xl p-6">

          {/* ── USERNAME LOGIN ── */}
          {tab === "local" && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Username</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                  <input
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                    placeholder="Enter username"
                    autoComplete="username"
                    className="w-full h-11 pl-9 pr-3 rounded-xl ring-1 ring-border bg-background text-sm outline-none focus:ring-brand transition-all"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                  <input
                    type={showPass ? "text" : "password"}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="current-password"
                    className="w-full h-11 pl-9 pr-10 rounded-xl ring-1 ring-border bg-background text-sm outline-none focus:ring-brand transition-all"
                  />
                  <button type="button" onClick={() => setShowPass(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showPass ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>

              {/* Remember me */}
              <label className="flex items-center gap-2.5 cursor-pointer group">
                <div
                  onClick={() => setRemember(v => !v)}
                  className={`size-4 rounded flex items-center justify-center ring-1 transition-all ${remember ? "bg-brand ring-brand" : "ring-border group-hover:ring-brand/50"}`}
                >
                  {remember && <svg className="size-2.5 text-white" viewBox="0 0 10 8" fill="none">
                    <path d="M1 4L3.5 6.5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>}
                </div>
                <span className="text-xs text-muted-foreground">Remember me</span>
              </label>

              <Button
                type="submit"
                disabled={loading}
                className="w-full h-11 text-white"
                style={{ background: "var(--gradient-brand)" }}
              >
                {loading
                  ? <><Loader2 className="size-4 animate-spin mr-2" /> Signing in...</>
                  : "Sign In"
                }
              </Button>
            </form>
          )}

          {/* ── GOOGLE ── */}
          {tab === "google" && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground text-center">
                Sign in with your Google account via Supabase OAuth.
              </p>
              <button
                onClick={handleGoogleLogin}
                className="w-full h-11 rounded-xl ring-1 ring-border bg-background flex items-center justify-center gap-3 text-sm font-medium hover:bg-muted/50 transition-all"
              >
                <Chrome className="size-5 text-blue-500" />
                Continue with Google
              </button>
            </div>
          )}

          {/* ── GUEST ── */}
          {tab === "guest" && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground text-center">
                Continue as a guest. Some features may be limited.
              </p>
              <Button
                onClick={() => {
                  localStorage.setItem("local_user", JSON.stringify({
                    name: "Guest",
                    email: "guest@local",
                    avatar: "",
                    role: "guest",
                  }));
                  toast.success("Welcome, Guest!");
                  navigate({ to: "/" });
                }}
                className="w-full h-11 text-white"
                style={{ background: "var(--gradient-brand)" }}
              >
                Continue as Guest
              </Button>
            </div>
          )}
        </div>

        {/* New user */}
        <p className="text-center text-xs text-muted-foreground mt-4">
          New installation?{" "}
          <button
            onClick={() => navigate({ to: "/setup" })}
            className="text-brand hover:underline font-medium"
          >
            Set up your account
          </button>
        </p>
      </div>
    </div>
  );
}
