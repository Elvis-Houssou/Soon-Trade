import { notFound } from "next/navigation";
import { useTranslations } from "next-intl";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { hrefFor, SPACES, type SpaceId } from "@/features/navigation/spaces";
import { routing } from "@/i18n/routing";

export function sectionParams(spaceId: SpaceId) {
  const sections = SPACES[spaceId].nav.filter((item) => item.slug && !item.live);
  return routing.locales.flatMap((locale) => sections.map((item) => ({ locale, section: item.slug })));
}

/** État vide des sections dont le module n'est pas encore livré. */
export function SectionPlaceholder({ spaceId, section }: { spaceId: SpaceId; section: string }) {
  const t = useTranslations();
  const item = SPACES[spaceId].nav.find((entry) => entry.slug === section);
  if (!item) notFound();
  const Icon = item.icon;

  return (
    <Card className="mx-auto mt-10 flex max-w-lg flex-col items-center px-8 py-12 text-center">
      <span className="grid size-14 place-items-center rounded-card bg-primary-soft text-primary-soft-foreground">
        <Icon className="size-6" aria-hidden />
      </span>
      <h1 className="mt-5 text-xl font-bold">{t(`nav.${item.key}`)}</h1>
      <p className="mt-2 text-muted-foreground">{t("placeholder.body", { phase: item.phase ?? 0 })}</p>
      <ButtonLink href={hrefFor(spaceId, "")} variant="outline" className="mt-6">
        {t("placeholder.back")}
      </ButtonLink>
    </Card>
  );
}
