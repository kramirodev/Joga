import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../lib/auth-context";
import { PLATFORM_ADMIN_CAPABILITY } from "../lib/features";
import { LoadingBlock } from "./Feedback";

/**
 * Portão das rotas administrativas.
 *
 * A sessão precisa declarar `platform.admin`. Sem a capability, a UI redireciona
 * para a raiz antes de disparar qualquer chamada a `/admin/*`.
 */
export function AdminRoute() {
  const { capabilities, loading } = useAuth();

  if (loading) {
    return <LoadingBlock label="Verificando permissão de administração..." />;
  }

  if (!capabilities.includes(PLATFORM_ADMIN_CAPABILITY)) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
