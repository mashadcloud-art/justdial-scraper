// Pure client-side entry for the Electron/desktop build — plain @tanstack/react-router
// RouterProvider + createRoot, no @tanstack/react-start import anywhere in this chain.
// Deliberately separate from src/client.tsx (the SSR hydration entry used by the web
// deploy), which pulls in Start's Node-only SSR runtime (node:async_hooks etc.) into
// the bundle and crashes the Electron BrowserWindow.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import { getRouter } from "./router";
import "./styles.css";

const router = getRouter();
const rootEl = document.getElementById("root")!;

createRoot(rootEl).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
);
