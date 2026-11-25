import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    // Same-origin in dev: the httpOnly session cookie works without CORS tricks.
    // xfwd: forward the browser's host (X-Forwarded-Host) so the API's same-site Origin check works
    // whichever address the app is opened from (localhost, 127.0.0.1, LAN IP).
    proxy: { "/api": { target: "http://localhost:8000", xfwd: true } },
  },
});
