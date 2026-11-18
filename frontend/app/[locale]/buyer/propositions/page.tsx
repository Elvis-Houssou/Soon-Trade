import { Suspense } from "react";
import { BuyerProposalsScreen } from "@/features/proposals/buyer-proposals";

export default function Page() {
  return (
    // L'écran lit `?id=` pour ouvrir directement une proposition.
    <Suspense>
      <BuyerProposalsScreen />
    </Suspense>
  );
}
