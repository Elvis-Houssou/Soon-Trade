import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { QueryProvider } from "@/components/auth/session";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { routing } from "@/i18n/routing";
import "../globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const manrope = Manrope({ variable: "--font-manrope", subsets: ["latin"] });

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "meta" });
  return {
    title: { default: "SOON TRADE", template: "%s · SOON TRADE" },
    description: t("description"),
    // Icônes de la planche de marque : clair ou sombre selon le thème du navigateur, dégradé sur l'écran d'accueil.
    icons: {
      icon: [
        { url: "/brand/icons/icon.svg", type: "image/svg+xml" },
        { url: "/brand/icons/icon-light-32.png", sizes: "32x32", media: "(prefers-color-scheme: light)" },
        { url: "/brand/icons/icon-dark-32.png", sizes: "32x32", media: "(prefers-color-scheme: dark)" },
      ],
      apple: "/brand/icons/icon-gradient-180.png",
    },
  };
}

export default async function RootLayout({ children, params }: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={`${inter.variable} ${manrope.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <NextIntlClientProvider>
          <ThemeProvider>
            <QueryProvider>{children}</QueryProvider>
          </ThemeProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
