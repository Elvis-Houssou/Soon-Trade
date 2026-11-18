"use client";

import { useQueryClient } from "@tanstack/react-query";
import { LogOut, Menu, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { type ReactNode, useEffect, useRef } from "react";
import { type Me, useLogout, useMe, useSpaceGuard } from "@/components/auth/session";
import { NotificationBell } from "@/components/shell/notification-bell";
import { api } from "@/lib/api";
import { Logo } from "@/components/brand/logo";
import { PageEnter, Sheen, useSlidingMarker } from "@/components/motion/motion";
import { LanguageSwitcher } from "@/components/theme/language-switcher";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { hrefFor, SPACES, type SpaceId } from "@/features/navigation/spaces";
import { Link, usePathname } from "@/i18n/navigation";
import { cn } from "@/lib/utils";

function Sidebar({
  spaceId,
  onNavigate,
  footer,
}: {
  spaceId: SpaceId;
  onNavigate?: () => void;
  /** Réglages ajoutés sous la navigation (menu mobile). */
  footer?: ReactNode;
}) {
  const t = useTranslations();
  const pathname = usePathname();
  const permissions = useMe().data?.permissions ?? [];
  const space = SPACES[spaceId];
  const SpaceIcon = space.icon;
  const navRoot = useRef<HTMLDivElement>(null);
  const marker = useRef<HTMLSpanElement>(null);
  useSlidingMarker(navRoot, marker, pathname);

  return (
    <div className="flex h-full flex-col gap-5 p-4">
      <Link href="/" className="self-center pt-2 text-sm" onClick={onNavigate}>
        <Logo />
      </Link>

      <div className="relative isolate flex items-center gap-3 overflow-hidden rounded-card bg-banner p-3 text-white shadow-raised">
        <Sheen />
        <SpaceIcon className="size-7 shrink-0" aria-hidden />
        <div className="min-w-0">
          <p className="truncate font-display font-bold">
            {t(`spaces.${spaceId}.name`)}
          </p>
          <p className="truncate text-xs text-white/80">
            {t(`spaces.${spaceId}.subtitle`)}
          </p>
        </div>
      </div>

      <nav
        aria-label={t(`spaces.${spaceId}.name`)}
        className="-mx-1 flex-1 overflow-y-auto px-1"
      >
        <div ref={navRoot} className="relative">
        <span
          ref={marker}
          aria-hidden
          className="pointer-events-none invisible absolute inset-x-0 top-0 rounded-control bg-primary-soft shadow-[inset_0_0_0_1px_color-mix(in_oklab,var(--primary)_22%,transparent)] after:absolute after:right-3 after:top-1/2 after:size-1.5 after:-translate-y-1/2 after:rounded-full after:bg-secondary after:shadow-[0_0_8px_1px_var(--secondary)]"
        />
        <ul className="space-y-0.5">
          {space.nav
            .filter(
              (item) =>
                !item.permission || permissions.includes(item.permission),
            )
            .map(({ slug, key, icon: Icon }) => {
              const href = hrefFor(spaceId, slug);
              const active = pathname === href;
              return (
                <li key={slug}>
                  <Link
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex items-center gap-3 rounded-control px-3 py-2 text-sm font-medium text-muted-foreground transition-colors duration-200 hover:bg-surface-muted hover:text-foreground",
                      // Le fond actif est porté par l'indicateur qui glisse, pas par le lien.
                      active &&
                        "font-semibold text-primary-soft-foreground hover:bg-transparent hover:text-primary-soft-foreground",
                    )}
                  >
                    <Icon className="size-[1.125rem] shrink-0" aria-hidden />
                    {t(`nav.${key}`)}
                  </Link>
                </li>
              );
            })}
        </ul>
        </div>
      </nav>
      {footer && <div className="flex flex-wrap gap-3 border-t border-border pt-4">{footer}</div>}
    </div>
  );
}

function MobileMenu({ spaceId }: { spaceId: SpaceId }) {
  const t = useTranslations("common");
  const dialog = useRef<HTMLDialogElement>(null);
  const pathname = usePathname();

  // Le <dialog> natif apporte le piège de focus et la fermeture par Échap.
  useEffect(() => dialog.current?.close(), [pathname]);

  return (
    <>
      <button
        type="button"
        aria-label={t("openMenu")}
        onClick={() => dialog.current?.showModal()}
        className="grid size-10 shrink-0 place-items-center rounded-control border border-border bg-surface lg:hidden"
      >
        <Menu className="size-5" aria-hidden />
      </button>
      <dialog
        ref={dialog}
        aria-label={t("menu")}
        onClick={(event) =>
          event.target === dialog.current && dialog.current?.close()
        }
        className="m-0 h-dvh max-h-none w-72 max-w-[85vw] bg-surface text-foreground backdrop:bg-[#0f172a]/50"
      >
        <button
          type="button"
          aria-label={t("closeMenu")}
          onClick={() => dialog.current?.close()}
          className="absolute right-3 top-3 grid size-9 place-items-center rounded-control hover:bg-surface-muted"
        >
          <X className="size-5" aria-hidden />
        </button>
        <Sidebar
          spaceId={spaceId}
          onNavigate={() => dialog.current?.close()}
          footer={
            <>
              <LanguageSwitcher />
              <ThemeToggle />
            </>
          }
        />
      </dialog>
    </>
  );
}

/** Coque commune aux trois espaces : seule la navigation change. */
export function AppShell({
  spaceId,
  children,
}: {
  spaceId: SpaceId;
  children: ReactNode;
}) {
  const t = useTranslations("common");
  const { me, failed } = useSpaceGuard(spaceId);
  const logout = useLogout();
  const pathname = usePathname();
  const locale = useLocale();
  const queryClient = useQueryClient();

  // Les e-mails partent dans la langue que l'utilisateur affiche en dernier.
  useEffect(() => {
    if (!me || me.locale === locale) return;
    api<Me>("/auth/me", { locale }, "PATCH")
      .then((updated) => queryClient.setQueryData(["me"], updated))
      .catch(() => undefined); // sans incidence sur l'affichage : on réessaiera au prochain écran
  }, [me, locale, queryClient]);

  // Rien de l'espace n'est affiché tant que la session n'est pas confirmée.
  if (!me) {
    return (
      <>
        <p
          role={failed ? "alert" : "status"}
          className="grid min-h-dvh place-items-center text-muted-foreground"
        >
          {failed ? t("unavailable") : t("loading")}
        </p>
        {/* Gardé dans l'arbre (masqué) pour que Next puisse préparer la navigation. */}
        <div hidden>{children}</div>
      </>
    );
  }

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[17rem_1fr]">
      <aside className="sticky top-0 hidden h-dvh border-r border-border bg-surface lg:block">
        <Sidebar spaceId={spaceId} />
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/85 px-4 py-3 backdrop-blur sm:px-6">
          <MobileMenu spaceId={spaceId} />
          <p className="ml-auto min-w-0 text-right text-sm leading-tight max-sm:hidden">
            <span className="block truncate font-semibold">{me.full_name}</span>
            <span className="block truncate text-muted-foreground">
              {me.organization.name}
            </span>
          </p>
          {/* Sur téléphone, langue et thème passent dans le menu : l'en-tête garde l'essentiel. */}
          <div className="shrink-0 max-sm:ml-auto">
            <NotificationBell />
          </div>
          <LanguageSwitcher className="max-sm:hidden" />
          <div className="max-sm:hidden">
            <ThemeToggle />
          </div>
          <button
            type="button"
            onClick={logout}
            aria-label={t("logout")}
            title={t("logout")}
            className="grid size-10 shrink-0 place-items-center rounded-full border border-border bg-surface text-muted-foreground transition-colors hover:text-foreground"
          >
            <LogOut className="size-4" aria-hidden />
          </button>
        </header>
        <main className="mx-auto w-full max-w-[90rem] px-4 py-6 sm:px-6">
          <PageEnter key={pathname}>{children}</PageEnter>
        </main>
      </div>
    </div>
  );
}
