import { Suspense } from "react";
import { InternalProposalsScreen } from "@/features/proposals/internal-proposals";

export default function Page() {
  return (
    // L'écran lit `?id=` pour ouvrir directement la proposition d'un dossier.
    <Suspense>
      <InternalProposalsScreen />
    </Suspense>
  );
}
