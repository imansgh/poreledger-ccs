import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

// Require an explicit destination: a published bundle must not call a visitor's localhost.
const apiUrl = process.env.NEXT_PUBLIC_CCS_API_URL;
let parsed;
try { parsed = new URL(apiUrl); } catch { /* handled below */ }
const localPreview = process.argv.includes("--local-preview");
const isLoopback = parsed && ["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname);
if (!parsed || parsed.username || parsed.password || parsed.search || parsed.hash ||
    !(parsed.protocol === "https:" || (localPreview && isLoopback && parsed.protocol === "http:")) ||
    (isLoopback && !localPreview)) {
  console.error("Set NEXT_PUBLIC_CCS_API_URL to the public HTTPS backend URL. For a local smoke test only, use a loopback URL and --local-preview.");
  process.exit(1);
}

const basePath = process.env.NEXT_PUBLIC_CCS_BASE_PATH ?? "/poreledger-ccs";
// Parent site allowed to receive the iframe-height message (components/EmbedHeight.tsx).
const embedOrigins = process.env.NEXT_PUBLIC_CCS_EMBED_ORIGINS ?? "https://imansgh.me";
const built = spawnSync(process.execPath, ["node_modules/next/dist/bin/next", "build"], {
  stdio: "inherit",
  env: { ...process.env, CCS_STATIC_EXPORT: "1", NEXT_PUBLIC_CCS_BASE_PATH: basePath,
    NEXT_PUBLIC_CCS_EMBED_ORIGINS: embedOrigins,
    NEXT_TELEMETRY_DISABLED: "1" },
});
if (built.error) throw built.error;
if (built.status !== 0) process.exit(built.status ?? 1);
// A published bundle must never call a visitor's own machine.
if (!localPreview) {
  // Loopback URLs only: the URL polyfill legitimately contains the bare word "localhost".
  const loopback = /\bhttps?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])/i;
  const offenders = [];
  const scan = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) scan(path);
      else if (/\.(html|js|json|txt|css)$/.test(entry.name) && loopback.test(readFileSync(path, "utf8"))) {
        offenders.push(path);
      }
    }
  };
  scan("out");
  if (offenders.length) {
    console.error(`Loopback URL found in the published bundle:\n  ${offenders.join("\n  ")}`);
    process.exit(1);
  }
}
// GitHub Pages otherwise ignores _next/. Other static hosts can also serve this output.
writeFileSync("out/.nojekyll", "");
writeFileSync("out/deployment-info.json", JSON.stringify({
  project: "PoreLedger CCS", base_path: basePath, api_url: apiUrl, embed_origins: embedOrigins,
  repo_url: process.env.NEXT_PUBLIC_CCS_REPO_URL || null,
  local_preview_only: Boolean(localPreview),
}, null, 2) + "\n");
console.log(`Static website: out/ → ${basePath || "/"}. API: ${apiUrl}`);
