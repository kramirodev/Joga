import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { installGlobalErrorReporting } from "./lib/telemetry";
import "./styles.css";

installGlobalErrorReporting();

const root = document.getElementById("root");
if (!root) {
  throw new Error("Elemento #root não encontrado");
}

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
