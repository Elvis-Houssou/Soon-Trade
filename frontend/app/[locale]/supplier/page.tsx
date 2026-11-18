import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { use } from "react";
import { SupplierDashboard } from "@/features/dashboard/dashboards";

export async function generateMetadata({ params }: PageProps<"/[locale]/supplier">): Promise<Metadata> {
  const t = await getTranslations({ locale: (await params).locale, namespace: "supplier" });
  return { title: t("title") };
}

/** Vue d'ensemble calculée sur les données réelles de l'espace (Phase 11). */
export default function SupplierOverview({ params }: PageProps<"/[locale]/supplier">) {
  setRequestLocale(use(params).locale);
  return <SupplierDashboard />;
}
