import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to the FastAPI backend so the frontend and
// backend can be developed independently without CORS friction.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.MINDBRIDGE_API ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
