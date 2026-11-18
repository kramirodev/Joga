import { useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth-context";
import { MODERATION_NOTIFICATIONS_ENABLED } from "../lib/features";
import { NotificationCenter } from "./NotificationCenter";
import { PasswordDialog } from "./PasswordDialog";
import { LogoutIcon, ShieldIcon } from "./ui/Icons";

export function AppHeader() {
  const { signOut, capabilities } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const moderationArea = location.pathname.startsWith("/moderation");
  const canModerate = capabilities.includes("moderation.read");
  const [passwordOpen, setPasswordOpen] = useState(false);

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <NavLink to={moderationArea ? "/moderation" : "/"} className="brand">
          <span className="brand__mark" aria-hidden="true">
            J
          </span>
          <span className="brand__text">
            JOGA <span>{moderationArea ? "y MODERAÇÃO" : "y GESTÃO"}</span>
          </span>
          <span className="sr-only"> — início</span>
        </NavLink>

        <nav className="app-nav" aria-label="Navegação principal">
          <NavLink
            to="/"
            className={({ isActive }) => (isActive ? "app-nav__link is-active" : "app-nav__link")}
          >
            Organizações
          </NavLink>
          {canModerate ? (
            <NavLink
              to="/moderation"
              className={({ isActive }) => (isActive ? "app-nav__link is-active" : "app-nav__link")}
            >
              <ShieldIcon size={16} />
              Moderação
            </NavLink>
          ) : null}
        </nav>

        <div className="app-header__actions">
          {canModerate && MODERATION_NOTIFICATIONS_ENABLED ? <NotificationCenter /> : null}
          <button
            type="button"
            className="button button--ghost button--compact"
            aria-label="Alterar senha"
            onClick={() => setPasswordOpen(true)}
          >
            <ShieldIcon size={16} />
            <span>Senha</span>
          </button>
          <button
            type="button"
            className="button button--ghost button--compact"
            onClick={handleSignOut}
          >
            <LogoutIcon size={16} />
            <span>Sair</span>
          </button>
        </div>
      </div>
      <PasswordDialog open={passwordOpen} onClose={() => setPasswordOpen(false)} />
    </header>
  );
}
