import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  publicDir: "arena-public",
  build: {
    outDir: "dist-arena",
    emptyOutDir: true,
    rollupOptions: { input: new URL("./arena.html", import.meta.url).pathname },
  },
  server: {
    host: "127.0.0.1",
    proxy: { "/api/arena": "http://127.0.0.1:8816" },
  },
});
