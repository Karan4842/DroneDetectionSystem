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
      "/live": "http://127.0.0.1:8000",
      "/analyze-image": "http://127.0.0.1:8000",
      "/detector": "http://127.0.0.1:8000",
      "/video_feed": "http://127.0.0.1:8000",
      "/sensors": "http://127.0.0.1:8000",
      "/countermeasures": "http://127.0.0.1:8000",
      "/analytics": "http://127.0.0.1:8000",
      "/report": "http://127.0.0.1:8000",
      "/demo": "http://127.0.0.1:8000"
    }
  }
});
