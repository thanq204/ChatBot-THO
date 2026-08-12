import { createContext, useCallback, useContext, useMemo, useState } from "react";

/**
 * Mock authentication. There is no auth service in the FastAPI backend, so this
 * checks a hardcoded account table in the browser and keeps the session in
 * localStorage. It proves out the login flow and the route guard, nothing more.
 *
 * Replace `signIn` with a real POST once the backend grows an auth route. The
 * rest of the app only touches the context, so nothing else has to change.
 */

const STORAGE_KEY = "acm-session";
const AuthContext = createContext(null);

/** Demo accounts. Shown on the login screen on purpose. */
export const DEMO_ACCOUNTS = [
  {
    email: "admin@community.ai",
    password: "demo12345",
    name: "Ngô Thái Tú",
    role: "Quản trị viên",
  },
  {
    email: "mod@community.ai",
    password: "demo12345",
    name: "Đặng Khánh Linh",
    role: "Kiểm duyệt viên",
  },
];

function readStoredSession() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && parsed.email ? parsed : null;
  } catch {
    // A corrupted entry must not take the whole app down on boot.
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredSession);

  const signIn = useCallback((email, password) => {
    const match = DEMO_ACCOUNTS.find(
      (account) =>
        account.email.toLowerCase() === email.trim().toLowerCase() && account.password === password,
    );
    if (!match) return { ok: false, error: "Email hoặc mật khẩu không đúng." };

    const session = { email: match.email, name: match.name, role: match.role };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    setUser(session);
    return { ok: true, user: session };
  }, []);

  const signOut = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, isAuthenticated: Boolean(user), signIn, signOut }),
    [user, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
