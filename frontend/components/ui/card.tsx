import { Link } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: ComponentProps<"section">) {
  return (
    <section
      className={cn("rounded-card border border-border bg-surface p-5 shadow-card", className)}
      {...props}
    />
  );
}

/** Carte titrée, avec lien « Voir tout » facultatif. */
export function SectionCard({
  title,
  href,
  action,
  className,
  children,
}: {
  title: string;
  href?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const t = useTranslations("common");
  return (
    <Card className={className}>
      <header className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold">{title}</h2>
        {action}
        {href && (
          <Link href={href} className="text-sm font-semibold text-primary-soft-foreground hover:underline">
            {t("seeAll")}
          </Link>
        )}
      </header>
      {children}
    </Card>
  );
}
