import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server owns the UI on :5173 and forwards API traffic to FastAPI on :8000,
// so the browser stays same-origin and no CORS preflight is needed while developing.
export default defineConfig({
  // Keep public VITE_* settings alongside backend settings at the repository root.
  envDir: "..",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    // Production source maps expose implementation details and are not needed
    // by this MVP's browser runtime.
    sourcemap: false,
  },
});
