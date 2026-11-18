"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", labelKey: "themeLight", icon: Sun },
  { value: "system", labelKey: "themeSystem", icon: Monitor },
  { value: "dark", labelKey: "themeDark", icon: Moon },
] as const;

const noop = () => () => {};

/** Sélecteur Light / Système / Dark de la planche de marque. */
export function ThemeToggle({ className }: { className?: string }) {
  const t = useTranslations("common");
  const { theme, setTheme } = useTheme();
  // Le thème choisi n'est connu que côté navigateur : rien n'est coché au rendu serveur.
  const mounted = useSyncExternalStore(noop, () => true, () => false);

  return (
    <div
      role="radiogroup"
      aria-label={t("themeLabel")}
      className={cn("inline-flex rounded-full border border-border bg-surface p-1", className)}
    >
      {OPTIONS.map(({ value, labelKey, icon: Icon }) => {
        const checked = mounted && theme === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={t(labelKey)}
            title={t(labelKey)}
            onClick={() => setTheme(value)}
            className={cn(
              "grid size-8 place-items-center rounded-full text-muted-foreground transition-colors hover:text-foreground",
              checked && "bg-primary text-primary-foreground hover:text-primary-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden />
          </button>
        );
      })}
    </div>
  );
}
