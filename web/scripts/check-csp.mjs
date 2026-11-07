import { readFile } from "node:fs/promises";

const htmlPath = new URL("../dist/index.html", import.meta.url);
const html = await readFile(htmlPath, "utf8");

const meta = html.match(/<meta http-equiv="Content-Security-Policy" content="([^"]+)"\s*\/?>/);

if (!meta) {
  throw new Error("CSP ausente em dist/index.html.");
}

const policy = meta[1];
const directives = [
  "default-src 'self'",
  "base-uri 'none'",
  "object-src 'none'",
  "script-src 'self'",
  "style-src 'self'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "form-action 'self'",
  "frame-src 'none'",
];

for (const directive of directives) {
  if (!policy.includes(directive)) {
    throw new Error(`Diretiva CSP ausente: ${directive}`);
  }
}

if (/unsafe-inline|unsafe-eval/.test(policy)) {
  throw new Error("A CSP do painel não pode permitir unsafe-inline ou unsafe-eval.");
}

if (policy.includes("frame-ancestors")) {
  throw new Error("frame-ancestors não é aplicado via <meta>; deve ser cabeçalho HTTP.");
}

const cspIndex = html.indexOf("Content-Security-Policy");
const firstScriptIndex = html.search(/<script[\s>]/i);
if (firstScriptIndex !== -1 && firstScriptIndex < cspIndex) {
  throw new Error("A CSP precisa aparecer antes de qualquer <script> no HTML.");
}

console.log("CSP do painel validada em dist/index.html.");
