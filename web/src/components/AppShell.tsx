import type { ReactNode } from "react";

import { AppHeader } from "./AppHeader";
import { useLocation } from "react-router-dom";

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const moderation = location.pathname.startsWith("/moderation");

  return (
    <div className="app-shell">
      <a className="skip-link" href="#conteudo">
        Pular para o conteúdo
      </a>
      <AppHeader />
      <main id="conteudo" className="page" tabIndex={-1}>
        {children}
      </main>
      <footer className="app-footer">
        <p>
          <strong>JOGA</strong> {moderation ? "y MODERAÇÃO" : "y GESTÃO"}
        </p>
        <p className="app-footer__note">
          {moderation
            ? "Ferramenta interna de moderação. Acesso restrito e auditado."
            : "Painel autenticado para as operações originadas no JOGA."}
        </p>
      </footer>
    </div>
  );
}
