import { useCallback, useEffect, useState } from "react";
import type { components } from "./api-types";

type S = components["schemas"];
export type Account = S["Account"];
export type Category = S["Category"];
export type Transaction = S["Transaction"];
export type TransactionPage = S["TransactionPage"];
export type NetWorth = S["NetWorth"];
export type CashFlow = S["CashFlow"];
export type Holding = S["Holding"];
export type Goal = S["Goal"];

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

/** Fetches `path` and refetches when it changes, keeping the previous data on screen meanwhile. */
export function useApi<T>(path: string | null) {
  const [state, setState] = useState<{ data?: T; error?: Error; loading: boolean }>({ loading: true });
  const [version, setVersion] = useState(0);
  useEffect(() => {
    if (!path) return;
    let live = true;
    setState((s) => ({ ...s, loading: true }));
    api<T>(path).then(
      (data) => live && setState({ data, loading: false }),
      (error) => live && setState((s) => ({ ...s, error, loading: false })),
    );
    return () => { live = false; };
  }, [path, version]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { ...state, reload };
}

export const qs = (params: Record<string, string | number | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};
export type ImportPreview = S["ImportPreview"];
export type ImportMapping = S["ImportMapping"];
export type ImportRow = S["ImportRow"];
export type ImportResult = S["ImportResult"];
export type ImportRecord = S["ImportRecord"];

export const post = <T,>(path: string, body: unknown) => api<T>(path, { method: "POST", body: JSON.stringify(body) });
