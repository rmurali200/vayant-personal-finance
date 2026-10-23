import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export const CURRENCIES = ["USD", "CAD", "INR"] as const;
export type Theme = "system" | "light" | "dark";

interface Settings {
  currency: string;
  setCurrency: (c: string) => void;
  theme: Theme;
  setTheme: (t: Theme) => void;
}

const Ctx = createContext<Settings | null>(null);

function stored<T extends string>(key: string, fallback: T): T {
  try { return (localStorage.getItem(key) as T) || fallback; } catch { return fallback; }
}
function store(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* private mode: keep in memory only */ }
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [currency, setCurrency] = useState<string>(() => stored("vayant.currency", "USD"));
  const [theme, setTheme] = useState<Theme>(() => stored<Theme>("vayant.theme", "system"));
  useEffect(() => store("vayant.currency", currency), [currency]);
  useEffect(() => {
    store("vayant.theme", theme);
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }, [theme]);
  return <Ctx.Provider value={{ currency, setCurrency, theme, setTheme }}>{children}</Ctx.Provider>;
}

export function useSettings() {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSettings outside SettingsProvider");
  return s;
}
