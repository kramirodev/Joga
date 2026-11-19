import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
    unstubGlobals: true,
    // O painel tem testes de interação com muitos `userEvent`; 15s evita
    // flutuação sob carga sem mascarar um teste travado de verdade.
    testTimeout: 15_000,
  },
});
