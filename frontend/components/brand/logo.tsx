import { cn } from "@/lib/utils";

/**
 * Logo approuvé (docs/design/Soon_logo). Le PNG blanc sert de masque : la couleur
 * vient du texte courant, donc un seul fichier couvre les thèmes clair et sombre.
 * shortcut: PNG 440×160 extrait de la planche, net jusqu'à ~220 px de large ;
 * remplacer par le SVG vectoriel d'origine dès qu'il existe.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <span
      role="img"
      aria-label="SOON TRADE"
      className={cn("block aspect-[440/160] w-[8em] bg-foreground", className)}
      style={{ mask: "url(/brand/soon-trade-logo.png) center / contain no-repeat" }}
    />
  );
}
