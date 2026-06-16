// vite.config.js
// Vite is the build tool and dev server for our React app.
// It's much faster than Create React App (CRA).

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],   // Enable React JSX transformation
  server: {
    port: 5173,         // Frontend runs at http://localhost:5173
  },
});