import { Suspense } from "react";
import { BuyerOrdersScreen } from "@/features/orders/buyer-orders";

export default function Page() {
  return (
    // L'écran lit `?id=` pour ouvrir directement une commande.
    <Suspense>
      <BuyerOrdersScreen />
    </Suspense>
  );
}
