import { setRequestLocale } from "next-intl/server";
import { SectionPlaceholder, sectionParams } from "@/components/shell/section-placeholder";

export function generateStaticParams() {
  return sectionParams("buyer");
}

export default async function Page({ params }: PageProps<"/[locale]/buyer/[section]">) {
  const { locale, section } = await params;
  setRequestLocale(locale);
  return <SectionPlaceholder spaceId="buyer" section={section} />;
}
