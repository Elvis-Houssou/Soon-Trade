import { Suspense } from "react";
import { SupplierOrdersScreen } from "@/features/orders/supplier-orders";

export default function Page() {
  return (
    // L'écran lit `?id=` pour ouvrir directement une commande.
    <Suspense>
      <SupplierOrdersScreen />
    </Suspense>
  );
}
