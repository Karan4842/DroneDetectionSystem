import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/config": "http://127.0.0.1:8000",
      "/summary": "http://127.0.0.1:8000",
      "/runtime": "http://127.0.0.1:8000",
      "/alerts": "http://127.0.0.1:8000",
      "/evidence": "http://127.0.0.1:8000",
      "/artifacts": "http://127.0.0.1:8000",
      "/analyze-image": "http://127.0.0.1:8000",
      "/detector": "http://127.0.0.1:8000"
    }
  }
});
