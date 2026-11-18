import { setRequestLocale } from "next-intl/server";
import { AppShell } from "@/components/shell/app-shell";

export default async function Layout({ children, params }: LayoutProps<"/[locale]/buyer">) {
  setRequestLocale((await params).locale);
  return <AppShell spaceId="buyer">{children}</AppShell>;
}
