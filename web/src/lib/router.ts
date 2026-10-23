import { useEffect, useState } from "react";

// Hash routing: the server serves one index.html and needs no fallback rules.
function read() {
  const [path, query = ""] = (location.hash.slice(1) || "/").split("?");
  return { path, params: new URLSearchParams(query) };
}

export function useRoute() {
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const onChange = () => { setRoute(read()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export const href = (path: string, params?: Record<string, string | number>) =>
  `#${path}${params ? "?" + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])) : ""}`;
