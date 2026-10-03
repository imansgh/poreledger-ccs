const basePath = process.env.NEXT_PUBLIC_CCS_BASE_PATH ?? "";
if (basePath && !/^\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*$/.test(basePath)) {
  throw new Error("NEXT_PUBLIC_CCS_BASE_PATH must be empty or a path like /poreledger-ccs (no trailing slash).");
}
const staticExport = process.env.CCS_STATIC_EXPORT === "1";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  basePath,
  ...(staticExport ? { output: "export", trailingSlash: true } : {}),
};
export default nextConfig;
