import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../lib/auth-context";
import { MODERATION_READ_CAPABILITY } from "../lib/features";
import { LoadingBlock } from "./Feedback";

/**
 * Portão da área de moderação.
 *
 * A sessão precisa declarar `moderation.read`. Sem a capability, a UI
 * redireciona para a raiz antes de disparar qualquer chamada a
 * `/moderation/*`.
 */
export function ModerationRoute() {
  const { capabilities, loading } = useAuth();

  if (loading) {
    return <LoadingBlock label="Verificando permissão de moderação..." />;
  }

  if (!capabilities.includes(MODERATION_READ_CAPABILITY)) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
