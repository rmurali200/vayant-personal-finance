// Generates src/styles/tokens.css from design/tokens.json (exported from the Vayant design system).
// Run after updating tokens.json: npm run tokens
import { readFileSync, writeFileSync } from "node:fs";

const t = JSON.parse(readFileSync(new URL("../design/tokens.json", import.meta.url)));
const val = (v) => String(v).replace(/^\{(.+)\}$/, "var(--$1)");
const themed = (tokens, theme) =>
  tokens.filter((x) => typeof x.value === "object" && x.value[theme]).map((x) => `  --${x.name}: ${val(x.value[theme])};`);
const plain = (tokens) =>
  tokens.map((x) => `  --${x.name}: ${val(typeof x.value === "object" ? x.value.light : x.value)};`);

const all = [...t.color.tokens, ...t.spacing.tokens, ...t.radius.tokens, ...t.shadow.tokens];
const families = Object.entries(t.type.families).map(([k, v]) => `  --font-${k}: ${v};`);
const dark = themed(all, "dark").join("\n");

writeFileSync(new URL("../src/styles/tokens.css", import.meta.url), `/* Generated from design/tokens.json by scripts/tokens.mjs. Do not edit. */
:root {
  color-scheme: light;
${[...plain(all), ...families].join("\n")}
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
  color-scheme: dark;
${dark}
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
${dark}
}
`);
