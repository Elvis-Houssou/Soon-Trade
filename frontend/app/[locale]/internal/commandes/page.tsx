import { Suspense } from "react";
import { InternalOrdersScreen } from "@/features/orders/internal-orders";

export default function Page() {
  return (
    // L'écran lit `?id=` pour ouvrir directement une commande.
    <Suspense>
      <InternalOrdersScreen />
    </Suspense>
  );
}
