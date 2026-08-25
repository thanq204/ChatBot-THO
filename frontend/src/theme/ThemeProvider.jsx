import { createContext, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "modai-theme";
const ThemeContext = createContext(null);

function getInitialTheme() {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(getInitialTheme);

  // Reflect the theme on the document, but do NOT write to storage here.
  // Writing on mount would stamp a key for everyone, and the media listener
  // below reads that key to decide whether the user has made an explicit
  // choice — so an unconditional write silently disabled following the OS.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event) => {
      if (window.localStorage.getItem(STORAGE_KEY)) return; // user already chose explicitly
      setTheme(event.matches ? "dark" : "light");
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const value = useMemo(
    () => ({
      theme,
      // Storage is written only by an explicit toggle. That write is what opts
      // the session out of following the OS from then on.
      toggleTheme: () =>
        setTheme((current) => {
          const next = current === "dark" ? "light" : "dark";
          try { window.localStorage.setItem(STORAGE_KEY, next); } catch { /* ignore */ }
          return next;
        }),
    }),
    [theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
