import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// O painel é servido do mesmo site da API, então tudo pode ficar em 'self'.
// O build extrai CSS e JS para arquivos externos; não há script ou estilo inline.
// `frame-ancestors` não funciona em <meta> e deve ser enviado pela hospedagem.
const PANEL_CSP = [
  "default-src 'self'",
  "base-uri 'none'",
  "object-src 'none'",
  "script-src 'self'",
  "style-src 'self'",
  "img-src 'self' data:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "form-action 'self'",
  "frame-src 'none'",
  "worker-src 'self'",
  "manifest-src 'self'",
].join("; ");

function cspPlugin(): Plugin {
  return {
    name: "joga-panel-csp",
    apply: "build",
    transformIndexHtml(html) {
      const charset = /<meta charset="[^"]*"\s*\/?>/i;
      if (!charset.test(html)) {
        throw new Error("index.html precisa declarar <meta charset> antes da CSP.");
      }
      return html.replace(
        charset,
        (tag) => `${tag}\n    <meta http-equiv="Content-Security-Policy" content="${PANEL_CSP}" />`,
      );
    },
  };
}

export default defineConfig({
  plugins: [react(), cspPlugin()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
