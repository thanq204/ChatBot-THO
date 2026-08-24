import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { auth, clearAccessToken, getAccessToken, setAccessToken } from "../api/client.js";

const STORAGE_KEY = "acm-session";
const AuthContext = createContext(null);

function readStoredSession() {
  try { return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null"); } catch { return null; }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredSession);
  useEffect(() => {
    if (!getAccessToken()) return;
    auth.me().then((account) => { setUser(account); window.localStorage.setItem(STORAGE_KEY, JSON.stringify(account)); }).catch(() => { clearAccessToken(); window.localStorage.removeItem(STORAGE_KEY); setUser(null); });
  }, []);
  const accept = useCallback((result) => {
    setAccessToken(result.access_token); setUser(result.user);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(result.user));
    return { ok: true, user: result.user };
  }, []);
  const signIn = useCallback(async (email, password) => {
    try { return accept(await auth.login({ email, password })); } catch (error) { return { ok: false, error: error.message }; }
  }, [accept]);
  const register = useCallback(async (payload) => {
    try { return accept(await auth.register(payload)); } catch (error) { return { ok: false, error: error.message }; }
  }, [accept]);
  const acceptInvite = useCallback(async (token, payload) => {
    try { return accept(await auth.acceptInvite(token, payload)); } catch (error) { return { ok: false, error: error.message }; }
  }, [accept]);
  const signOut = useCallback(() => { clearAccessToken(); window.localStorage.removeItem(STORAGE_KEY); setUser(null); }, []);
  const updateProfile = useCallback(async (payload) => {
    try {
      const account = await auth.updateMe(payload);
      setUser(account); window.localStorage.setItem(STORAGE_KEY, JSON.stringify(account));
      return { ok: true, user: account };
    } catch (error) { return { ok: false, error: error.message }; }
  }, []);
  const value = useMemo(() => ({ user, isAuthenticated: Boolean(user && getAccessToken()), signIn, register, acceptInvite, signOut, updateProfile }), [user, signIn, register, acceptInvite, signOut, updateProfile]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { const context = useContext(AuthContext); if (!context) throw new Error("useAuth must be used inside AuthProvider"); return context; }
