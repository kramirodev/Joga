import { useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth-context";
import { MODERATION_NOTIFICATIONS_ENABLED, PLATFORM_ADMIN_CAPABILITY } from "../lib/features";
import { NotificationCenter } from "./NotificationCenter";
import { PasswordDialog } from "./PasswordDialog";
import { ClockIcon, LogoutIcon, MapPinIcon, ShieldIcon, SparkIcon, UsersIcon } from "./ui/Icons";

export function AppHeader() {
  const { signOut, capabilities } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const moderationArea = location.pathname.startsWith("/moderation");
  const adminArea = location.pathname.startsWith("/admin");
  const canModerate = capabilities.includes("moderation.read");
  const canAdmin = capabilities.includes(PLATFORM_ADMIN_CAPABILITY);
  // Administradores da plataforma também precisam descobrir a área de moderação.
  // A autorização real continua no servidor (GET /moderation/me).
  const showModerationLink = canModerate || canAdmin;
  const [passwordOpen, setPasswordOpen] = useState(false);

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  const areaLabel = adminArea ? "y ADMINISTRAÇÃO" : moderationArea ? "y MODERAÇÃO" : "y GESTÃO";

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <NavLink
          to={adminArea && canAdmin ? "/admin/users" : moderationArea ? "/moderation" : "/"}
          className="brand"
        >
          <span className="brand__mark" aria-hidden="true">
            J
          </span>
          <span className="brand__text">
            JOGA <span>{areaLabel}</span>
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
          {showModerationLink ? (
            <NavLink
              to="/moderation"
              className={({ isActive }) => (isActive ? "app-nav__link is-active" : "app-nav__link")}
            >
              <ShieldIcon size={16} />
              Moderação
            </NavLink>
          ) : null}
          {canAdmin ? (
            <>
              <NavLink
                to="/admin/users"
                className={({ isActive }) =>
                  isActive ? "app-nav__link is-active" : "app-nav__link"
                }
              >
                <UsersIcon size={16} />
                Usuários
              </NavLink>
              <NavLink
                to="/admin/sports"
                className={({ isActive }) =>
                  isActive ? "app-nav__link is-active" : "app-nav__link"
                }
              >
                <SparkIcon size={16} />
                Esportes
              </NavLink>
              <NavLink
                to="/admin/venues"
                className={({ isActive }) =>
                  isActive ? "app-nav__link is-active" : "app-nav__link"
                }
              >
                <MapPinIcon size={16} />
                Quadras
              </NavLink>
              <NavLink
                to="/admin/observability"
                className={({ isActive }) =>
                  isActive ? "app-nav__link is-active" : "app-nav__link"
                }
              >
                <ClockIcon size={16} />
                Monitoramento
              </NavLink>
            </>
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
