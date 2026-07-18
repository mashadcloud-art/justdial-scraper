import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tsconfigPaths(), tailwindcss()],
  build: {
    outDir: 'dist/client',
    emptyOutDir: true,
  },
  server: {
    port: 8080,
    strictPort: true,
    allowedHosts: ["scrapper.mashad.shop"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 8080,
    strictPort: true,
    allowedHosts: ["scrapper.mashad.shop"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
