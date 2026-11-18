import { setRequestLocale } from "next-intl/server";
import { SectionPlaceholder, sectionParams } from "@/components/shell/section-placeholder";

export function generateStaticParams() {
  return sectionParams("internal");
}

export default async function Page({ params }: PageProps<"/[locale]/internal/[section]">) {
  const { locale, section } = await params;
  setRequestLocale(locale);
  return <SectionPlaceholder spaceId="internal" section={section} />;
}
