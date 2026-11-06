import { createContext, useContext } from "react";

import type { WebSessionPayload, WebUser } from "../types";

export interface AuthContextValue {
  user: WebUser | null;
  loading: boolean;
  signIn: (payload: WebSessionPayload) => void;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth deve ser usado dentro de AuthProvider");
  }
  return context;
}
