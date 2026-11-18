import type { Locale } from "./routing";

const GERMAN = "DE AT LI";
// Pays où le français est langue officielle ou d'usage courant dans les affaires.
const FRENCH =
  "FR CI SN ML BF NE TG BJ GN CM GA CG CD TD CF MG DJ KM BI RW HT MC LU MA DZ TN MR GQ SC VU NC PF RE GP MQ GF YT";
// Pays plurilingues : la langue du navigateur est un meilleur indice que le pays.
const AMBIGUOUS = "CH BE CA";

/**
 * Langue initiale d'après le pays de l'adresse IP. `undefined` signifie « pas d'avis » :
 * l'appelant retombe alors sur la langue du navigateur, puis sur le français.
 */
export function localeForCountry(country: string | null | undefined): Locale | undefined {
  const code = country?.trim().toUpperCase();
  if (!code || code.length !== 2 || code === "XX" || AMBIGUOUS.includes(code)) return undefined;
  if (GERMAN.includes(code)) return "de";
  if (FRENCH.includes(code)) return "fr";
  return "en";
}
