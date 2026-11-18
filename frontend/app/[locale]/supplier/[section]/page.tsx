import { setRequestLocale } from "next-intl/server";
import { SectionPlaceholder, sectionParams } from "@/components/shell/section-placeholder";

export function generateStaticParams() {
  return sectionParams("supplier");
}

export default async function Page({ params }: PageProps<"/[locale]/supplier/[section]">) {
  const { locale, section } = await params;
  setRequestLocale(locale);
  return <SectionPlaceholder spaceId="supplier" section={section} />;
}
