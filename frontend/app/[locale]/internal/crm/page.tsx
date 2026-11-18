import { Suspense } from "react";
import { CrmScreen } from "@/features/crm/crm-screen";

export default function Page() {
  return (
    // L'écran lit l'adresse (`?id=`, `?new=`) pour ouvrir directement un fil.
    <Suspense>
      <CrmScreen />
    </Suspense>
  );
}
