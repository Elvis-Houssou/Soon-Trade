import createMiddleware from "next-intl/middleware";
import { type NextRequest, NextResponse } from "next/server";
import { localeForCountry } from "./i18n/country-locale";
import { routing } from "./i18n/routing";

const handleI18n = createMiddleware(routing);

/**
 * Ordre de choix de la langue : préfixe d'URL, puis choix déjà fait (cookie),
 * puis pays de l'adresse IP, puis langue du navigateur, puis français.
 * Le pays est fourni par l'hébergeur : en-tête Vercel ou Cloudflare, absent en local.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasLocalePrefix = routing.locales.some((l) => pathname === `/${l}` || pathname.startsWith(`/${l}/`));

  if (!hasLocalePrefix && !request.cookies.has("NEXT_LOCALE")) {
    const country = request.headers.get("x-vercel-ip-country") ?? request.headers.get("cf-ipcountry");
    const locale = localeForCountry(country);
    if (locale) {
      const url = request.nextUrl.clone();
      url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
      return NextResponse.redirect(url);
    }
  }
  return handleI18n(request);
}

export const config = {
  // Tout sauf les fichiers statiques et les routes internes de Next.
  matcher: "/((?!api|_next|_vercel|.*\\..*).*)",
};
