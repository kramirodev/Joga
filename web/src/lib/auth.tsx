import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { SESSION_EXPIRED_EVENT, refreshSession, webLogout } from "../lib/api";
import { AuthContext, type AuthContextValue } from "../lib/auth-context";
import type { WebSessionPayload, WebUser } from "../types";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<WebUser | null>(null);
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

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
    setSessionExpired(false);
  }, []);

  useEffect(() => {
    function handleExpired() {
      setUser(null);
      setCapabilities([]);
      setSessionExpired(true);
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, handleExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleExpired);
  }, []);

  const signOut = useCallback(async () => {
    await webLogout();
    setUser(null);
    setCapabilities([]);
    setSessionExpired(false);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, capabilities, loading, sessionExpired, signIn, signOut }),
    [user, capabilities, loading, sessionExpired, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
