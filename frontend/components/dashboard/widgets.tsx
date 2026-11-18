import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { AnimatedNumber } from "@/components/dashboard/animated-number";
import { Sheen } from "@/components/motion/motion";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function PageHeading({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="mb-5">
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="mt-1 text-muted-foreground">{description}</p>
    </div>
  );
}

/** Bandeau d'appel à l'action. Le visuel photo des maquettes viendra s'y superposer. */
export function HeroBanner({
  title,
  points,
  cta,
  image,
}: {
  title: string;
  points: { icon: LucideIcon; label: string }[];
  cta: { href: string; label: string };
  image: "port" | "marchandises";
}) {
  return (
    <section className="relative isolate overflow-hidden rounded-panel bg-banner px-6 py-8 text-white sm:px-10">
      {/* Décoratif : fondu à gauche dans le dégradé pour garder le texte lisible. */}
      <div
        aria-hidden
        className="absolute inset-y-0 right-0 -z-10 w-3/5 bg-cover bg-center max-sm:hidden"
        style={{
          backgroundImage: `url(/brand/soon-trade-${image}.webp)`,
          maskImage: "linear-gradient(to right, transparent, black 45%)",
        }}
      />
      <Sheen />
      <h2 className="max-w-xl text-2xl font-bold text-balance sm:text-3xl">
        {title}
      </h2>
      <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm text-white/90">
        {points.map(({ icon: Icon, label }) => (
          <li key={label} className="flex items-center gap-2">
            <Icon className="size-4" aria-hidden />
            {label}
          </li>
        ))}
      </ul>
      <ButtonLink
        href={cta.href}
        variant="inverse"
        className="mt-6 rounded-full"
      >
        {cta.label}
      </ButtonLink>
    </section>
  );
}

export function StatCard({
  icon: Icon,
  label,
  value,
  suffix,
  footnote,
}: {
  icon: LucideIcon;
  label: string;
  value: number;
  suffix?: string;
  footnote?: ReactNode;
}) {
  return (
    <Card>
      <div className="flex items-center gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-control bg-primary-soft text-primary-soft-foreground">
          <Icon className="size-5" aria-hidden />
        </span>
        <p className="text-sm font-medium leading-tight text-muted-foreground">
          {label}
        </p>
      </div>
      <p className="tabular mt-3 flex flex-wrap items-baseline gap-x-1.5 font-display text-2xl font-extrabold">
        <AnimatedNumber value={value} />
        {suffix && <span className="text-sm font-bold">{suffix}</span>}
      </p>
      {footnote && <div className="mt-1.5 text-xs">{footnote}</div>}
    </Card>
  );
}

export function StatGrid({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "grid gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5",
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * Tableau qui se replie en fiches sous 640 px : chaque cellule reprend alors
 * l'intitulé de sa colonne.
 */
export function DataTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: { key: string; cells: ReactNode[] }[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="max-sm:sr-only">
          <tr className="bg-surface-muted text-left text-xs text-muted-foreground">
            {columns.map((column) => (
              <th
                key={column}
                scope="col"
                className="px-3 py-2 font-semibold first:rounded-l-lg last:rounded-r-lg"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className="border-b border-border last:border-0 max-sm:grid max-sm:grid-cols-2 max-sm:gap-x-3 max-sm:py-3"
            >
              {row.cells.map((cell, index) => (
                <td
                  key={columns[index]}
                  className="px-3 py-3 max-sm:px-0 max-sm:py-1"
                >
                  <span className="block text-xs text-muted-foreground sm:hidden">
                    {columns[index]}
                  </span>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
