import type { ReactNode } from "react";
import { href, useRoute } from "./lib/router";
import { CURRENCIES, useSettings } from "./lib/settings";
import { Accounts } from "./pages/Accounts";
import { CashFlow } from "./pages/CashFlow";
import { Goals } from "./pages/Goals";
import { Investments } from "./pages/Investments";
import { Overview } from "./pages/Overview";
import { Transactions } from "./pages/Transactions";
import { Segmented } from "./ui/components";
import { Icon, type IconName } from "./ui/Icon";

// `converts`: the page shows amounts in the reporting currency, so it gets the currency switch.
const PAGES: { path: string; title: string; icon: IconName; converts?: boolean; render: (p: URLSearchParams) => ReactNode }[] = [
  { path: "/", title: "Overview", icon: "overview", converts: true, render: () => <Overview /> },
  { path: "/accounts", title: "Accounts", icon: "accounts", converts: true, render: () => <Accounts /> },
  { path: "/transactions", title: "Transactions", icon: "transactions", render: (p) => <Transactions params={p} /> },
  { path: "/cash-flow", title: "Cash flow", icon: "cashflow", converts: true, render: () => <CashFlow /> },
  { path: "/investments", title: "Investments", icon: "investments", converts: true, render: () => <Investments /> },
  { path: "/goals", title: "Goals", icon: "goals", render: () => <Goals /> },
];

export function App() {
  const { path, params } = useRoute();
  const { currency, setCurrency, theme, setTheme } = useSettings();
  const page = PAGES.find((p) => p.path === path) ?? PAGES[0];
  const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);

  const nav = (cls: string) => (
    <nav className={cls} aria-label="Main">
      {PAGES.map((p) => (
        <a key={p.path} href={href(p.path)} aria-current={p === page ? "page" : undefined}>
          <Icon name={p.icon} /><span>{p.title}</span>
        </a>
      ))}
    </nav>
  );

  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href={href("/")}><img src="/vayant-mark.webp" alt="" width={32} height={32} />Vayant</a>
        {nav("sidenav")}
      </aside>
      <div className="main">
        <header className="topbar">
          <a className="brand brand-compact" href={href("/")} aria-label="Vayant overview"><img src="/vayant-mark.webp" alt="" width={28} height={28} /></a>
          <h1 className="title-1">{page.title}</h1>
          <div className="topbar-tools">
            {page.converts && <Segmented label="Reporting currency" options={CURRENCIES} value={currency as (typeof CURRENCIES)[number]} onChange={setCurrency} />}
            <button type="button" className="icon-btn" onClick={() => setTheme(dark ? "light" : "dark")}
              aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}>
              <Icon name={dark ? "sun" : "moon"} />
            </button>
          </div>
        </header>
        <main className="content" key={page.path}>{page.render(params)}</main>
      </div>
      {nav("tabbar")}
    </div>
  );
}
