import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";
import { Logo } from "@/components/brand/logo";
import { AuthMotion } from "@/components/motion/public-motion";
import { LanguageSwitcher } from "@/components/theme/language-switcher";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { Card } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";

/** Cadre commun aux écrans de connexion, d'invitation et de mot de passe. */
export default async function AuthLayout({ children, params }: LayoutProps<"/[locale]">) {
  setRequestLocale((await params).locale);
  return (
    <AuthMotion>
      <main data-m-pre className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-10">
        <Link href="/" data-m="logo" className="self-center text-base">
          <Logo />
        </Link>
        <Card data-m="card" className="p-6 shadow-raised">
          {/* Les formulaires lisent l'URL côté navigateur. */}
          <Suspense>{children}</Suspense>
        </Card>
        <div data-m="controls" className="flex justify-center gap-3">
          {/* Lit l'adresse courante, inconnue au prérendu des pages à jeton. */}
          <Suspense>
            <LanguageSwitcher />
          </Suspense>
          <ThemeToggle />
        </div>
      </main>
    </AuthMotion>
  );
}
