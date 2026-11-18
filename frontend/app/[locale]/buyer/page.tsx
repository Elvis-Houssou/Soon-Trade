import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { use } from "react";
import { BuyerDashboard } from "@/features/dashboard/dashboards";

export async function generateMetadata({ params }: PageProps<"/[locale]/buyer">): Promise<Metadata> {
  const t = await getTranslations({ locale: (await params).locale, namespace: "buyer" });
  return { title: t("title") };
}

/** Vue d'ensemble calculée sur les données réelles de l'espace (Phase 11). */
export default function BuyerOverview({ params }: PageProps<"/[locale]/buyer">) {
  setRequestLocale(use(params).locale);
  return <BuyerDashboard />;
}
