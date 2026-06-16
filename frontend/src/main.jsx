// main.jsx – React entry point
// ReactDOM mounts the entire app into the <div id="root"> in index.html

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";

// StrictMode helps catch bugs during development
// It double-invokes some functions to detect side effects
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);