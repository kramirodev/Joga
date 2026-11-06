import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth-context";

export function AppHeader({ subtitle }: { subtitle?: string }) {
  const { signOut } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <header className="app-header">
      <div className="app-header__brand">
        <Link to="/" className="brand" aria-label="JOGA y GESTÃO — início">
          JOGA <span>y GESTÃO</span>
        </Link>
        {subtitle ? <p className="app-header__subtitle">{subtitle}</p> : null}
      </div>
      <button type="button" className="button button--ghost" onClick={handleSignOut}>
        Sair
      </button>
    </header>
  );
}
