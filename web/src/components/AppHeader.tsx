import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth-context";

export function AppHeader({
  subtitle,
  moderation = false,
}: {
  subtitle?: string;
  moderation?: boolean;
}) {
  const { signOut } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <header className="app-header">
      <div className="app-header__brand">
        <Link
          to={moderation ? "/moderation" : "/"}
          className="brand"
          aria-label={moderation ? "JOGA y MODERAÇÃO — início" : "JOGA y GESTÃO — início"}
        >
          JOGA <span>{moderation ? "y MODERAÇÃO" : "y GESTÃO"}</span>
        </Link>
        {subtitle ? <p className="app-header__subtitle">{subtitle}</p> : null}
      </div>
      <div className="app-header__actions">
        {moderation ? (
          <Link to="/" className="button button--ghost">
            Gestão
          </Link>
        ) : (
          <Link to="/moderation" className="button button--ghost">
            Moderação
          </Link>
        )}
        <button type="button" className="button button--ghost" onClick={handleSignOut}>
          Sair
        </button>
      </div>
    </header>
  );
}
