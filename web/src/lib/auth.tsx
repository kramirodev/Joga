import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { refreshSession, webLogout } from "../lib/api";
import { AuthContext, type AuthContextValue } from "../lib/auth-context";
import type { WebSessionPayload, WebUser } from "../types";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<WebUser | null>(null);
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const session = await refreshSession();
        if (!cancelled) {
          setUser(session?.user ?? null);
          setCapabilities(session?.capabilities ?? []);
        }
      } catch {
        if (!cancelled) {
          setUser(null);
          setCapabilities([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback((payload: WebSessionPayload) => {
    setUser(payload.user);
    setCapabilities(payload.capabilities);
  }, []);

  const signOut = useCallback(async () => {
    await webLogout();
    setUser(null);
    setCapabilities([]);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, capabilities, loading, signIn, signOut }),
    [user, capabilities, loading, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
