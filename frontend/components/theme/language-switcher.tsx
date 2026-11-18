"use client";

import { useLocale, useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { cn } from "@/lib/utils";

/** Change de langue en restant sur la même page ; le choix est mémorisé par cookie. */
export function LanguageSwitcher({ className }: { className?: string }) {
  const t = useTranslations("common");
  const current = useLocale();
  const pathname = usePathname();

  return (
    <nav
      aria-label={t("languageLabel")}
      className={cn("inline-flex rounded-full border border-border bg-surface p-1", className)}
    >
      {routing.locales.map((locale) => (
        <Link
          key={locale}
          href={pathname}
          locale={locale}
          hrefLang={locale}
          aria-current={locale === current ? "true" : undefined}
          className={cn(
            "grid h-8 min-w-8 place-items-center rounded-full px-2 text-xs font-semibold uppercase text-muted-foreground transition-colors hover:text-foreground",
            locale === current && "bg-primary text-primary-foreground hover:text-primary-foreground",
          )}
        >
          {locale}
        </Link>
      ))}
    </nav>
  );
}
