import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth": "http://127.0.0.1:8000",
      "/admin": "http://127.0.0.1:8000",
      "/trade": "http://127.0.0.1:8000",
      "/state": "http://127.0.0.1:8000",
      "/quiz": "http://127.0.0.1:8000",
      "/risk_elicitation": "http://127.0.0.1:8000",
      "/debrief": "http://127.0.0.1:8000",
      "/tournament": "http://127.0.0.1:8000",
      "/socket.io": {
        target: "http://127.0.0.1:8000",
        ws: true
      }
    }
  }
});
