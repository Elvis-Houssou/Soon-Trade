import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { use } from "react";
import { InternalDashboard } from "@/features/dashboard/dashboards";

export async function generateMetadata({ params }: PageProps<"/[locale]/internal">): Promise<Metadata> {
  const t = await getTranslations({ locale: (await params).locale, namespace: "internal" });
  return { title: t("title") };
}

/** Vue d'ensemble calculée sur les données réelles de l'espace (Phase 11). */
export default function InternalOverview({ params }: PageProps<"/[locale]/internal">) {
  setRequestLocale(use(params).locale);
  return <InternalDashboard />;
}
