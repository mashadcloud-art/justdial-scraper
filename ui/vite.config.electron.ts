// Electron/desktop-only build config. Emits a static dist/client (index.html + assets)
// that the packaged FastAPI backend serves directly to the Electron BrowserWindow.
//
// Deliberately kept separate from vite.config.ts, which is the TanStack Start SSR
// config used by the web deployment at scrapper.mashad.shop (Nitro server, no static
// index.html, and no tanstackStart/nitro plugin here) — do not merge these or point
// the web deploy at this file. The HTML entry (electron/index.html) loads
// src/client.electron.tsx, a plain @tanstack/react-router RouterProvider — never
// import @tanstack/react-start here, it pulls Node-only SSR runtime (node:async_hooks)
// into the browser bundle and crashes the Electron BrowserWindow.
import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import tailwindcss from "@tailwindcss/vite";

const root = resolve(__dirname, "electron");

export default defineConfig({
  root,
  plugins: [react(), tsconfigPaths({ root: __dirname }), tailwindcss()],
  build: {
    outDir: resolve(__dirname, "dist/client"),
    emptyOutDir: true,
  },
  server: {
    port: 8080,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
