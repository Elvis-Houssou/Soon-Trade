import { Handshake, Search, ShieldCheck, Truck } from "lucide-react";
import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { Logo } from "@/components/brand/logo";
import { Sheen } from "@/components/motion/motion";
import { HomeMotion } from "@/components/motion/public-motion";
import { LanguageSwitcher } from "@/components/theme/language-switcher";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { ButtonLink } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";

const SERVICE_ICONS = [Search, Handshake, ShieldCheck, Truck];

export default function HomePage({ params }: PageProps<"/[locale]">) {
  setRequestLocale(use(params).locale);
  const t = useTranslations("home");

  return (
    <HomeMotion>
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <header data-m="header" data-m-pre className="flex flex-wrap items-center gap-x-4 gap-y-3 py-5">
          <Link href="/" className="text-sm">
            <Logo />
          </Link>
          <nav aria-label={t("mainNav")} className="ml-auto hidden items-center gap-1 text-sm font-medium md:flex">
            <a href="#services" className="rounded-full px-4 py-2 transition-colors hover:bg-primary-soft">{t("services")}</a>
            <a href="#processus" className="rounded-full px-4 py-2 transition-colors hover:bg-primary-soft">{t("process")}</a>
          </nav>
          <LanguageSwitcher className="max-md:ml-auto" />
          <ThemeToggle />
          <ButtonLink href="/connexion">{t("login")}</ButtonLink>
        </header>

        <main>
          <section
            data-m="hero"
            data-m-pre
            className="relative isolate mt-4 overflow-hidden rounded-panel border border-border bg-surface px-6 py-14 shadow-card sm:px-12 sm:py-20"
          >
            {/* Un visuel par thème : chacun se fond dans la couleur de surface du sien. */}
            {(["clair", "sombre"] as const).map((theme) => (
              <div
                key={theme}
                data-m="hero-media"
                aria-hidden
                className={`absolute -inset-y-[6%] right-0 -z-10 w-3/5 bg-cover bg-center max-lg:hidden ${theme === "clair" ? "dark:hidden" : "hidden dark:block"}`}
                style={{
                  backgroundImage: `url(/brand/soon-trade-hero-${theme}.webp)`,
                  maskImage: "linear-gradient(to right, transparent, black 40%)",
                }}
              />
            ))}
            {/* Halo de marque : dérive au repos, suit le pointeur. */}
            <div
              data-m="glow"
              aria-hidden
              className="pointer-events-none absolute left-1/3 top-1/4 -z-10 size-80 rounded-full bg-[radial-gradient(circle,color-mix(in_oklab,var(--secondary)_35%,transparent),color-mix(in_oklab,var(--primary)_22%,transparent)_45%,transparent_70%)] blur-2xl"
            />
            <div className="relative max-w-2xl">
              <p data-m="badge" className="inline-block rounded-full bg-primary-soft px-4 py-1.5 text-sm font-semibold text-primary-soft-foreground">
                {t("badge")}
              </p>
              <h1 data-m="title" className="mt-6 text-[clamp(1.5rem,7.5vw,2.25rem)] font-extrabold leading-[1.1] text-balance sm:text-6xl">
                {t("titleLead")} <span className="text-primary">{t("titleAccent")}</span>
              </h1>
              <p data-m="lead" className="mt-6 max-w-xl text-lg text-muted-foreground">{t("lead")}</p>
              <div data-m="cta" className="mt-8 flex flex-wrap gap-3">
                <ButtonLink href="/connexion" size="lg" className="relative overflow-hidden">
                  <Sheen />
                  {t("ctaSubmit")}
                </ButtonLink>
                <a
                  href="#services"
                  className="inline-flex h-12 items-center rounded-control border border-primary/40 bg-surface px-6 font-semibold transition-colors hover:bg-primary-soft"
                >
                  {t("ctaDiscover")}
                </a>
              </div>
            </div>
          </section>

          <section id="services" className="scroll-mt-8 py-16">
            <h2 data-m="reveal" className="text-3xl font-bold">{t("servicesTitle")}</h2>
            <ul className="mt-8 grid gap-x-10 gap-y-8 sm:grid-cols-2">
              {SERVICE_ICONS.map((Icon, index) => (
                <li key={index} data-m="service" className="flex gap-4">
                  <span data-m="icon" className="grid size-12 shrink-0 place-items-center rounded-control bg-primary-soft text-primary-soft-foreground">
                    <Icon className="size-5" aria-hidden />
                  </span>
                  <div>
                    <h3 className="text-lg font-bold">{t(`service${index + 1}Title`)}</h3>
                    <p className="mt-1 text-muted-foreground">{t(`service${index + 1}Text`)}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section id="processus" className="scroll-mt-8 border-t border-border py-16">
            <h2 data-m="reveal" className="text-3xl font-bold">{t("processTitle")}</h2>
            <ol className="relative mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {/* Fil d'avancement tracé au défilement (grand écran). */}
              <span
                data-m="track"
                aria-hidden
                className="absolute inset-x-0 top-5 hidden h-px origin-left bg-gradient-to-r from-primary via-secondary to-transparent lg:block"
              />
              {[1, 2, 3, 4].map((step) => (
                <li key={step} data-m="step" className="relative">
                  <span className="tabular relative inline-grid size-10 place-items-center rounded-full bg-background font-display text-4xl font-extrabold text-primary">
                    {step}
                  </span>
                  <h3 className="mt-3 text-lg font-bold">{t(`step${step}Title`)}</h3>
                  <p className="mt-1 text-muted-foreground">{t(`step${step}Text`)}</p>
                </li>
              ))}
            </ol>
          </section>
        </main>

        <footer className="border-t border-border py-8 text-sm text-muted-foreground">{t("footer")}</footer>
      </div>
    </HomeMotion>
  );
}
