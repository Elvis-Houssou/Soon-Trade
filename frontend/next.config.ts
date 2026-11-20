import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const production = process.env.NODE_ENV === "production";
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// En ligne, l'API passe par le même domaine que le site (« /api », relayé vers Render) :
// le cookie de session reste alors un cookie du site, que les navigateurs envoient toujours.
const apiOrigin = apiUrl.startsWith("/") ? "" : new URL(apiUrl).origin;
const apiProxyTarget = process.env.API_PROXY_TARGET;

// CSP sans nonce (guide Next « Without Nonces ») : les pages restent statiques et en cache.
// shortcut: 'unsafe-inline' pour les scripts d'hydratation ; passer aux nonces si une
// exigence de conformité l'impose (rendu dynamique de toutes les pages).
const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data:",
  "font-src 'self'",
  `connect-src 'self' ${apiOrigin}`.trim(),
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "upgrade-insecure-requests",
].join("; ");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  // En développement, le rechargement à chaud et l'API en http seraient bloqués.
  ...(production ? [{ key: "Content-Security-Policy", value: contentSecurityPolicy }] : []),
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return apiProxyTarget ? [{ source: "/api/:path*", destination: `${apiProxyTarget}/:path*` }] : [];
  },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default createNextIntlPlugin()(nextConfig);
