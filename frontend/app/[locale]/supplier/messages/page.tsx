import { Suspense } from "react";
import { ClientMessagesScreen } from "@/features/messaging/messages";

export default function Page() {
  return (
    // L'écran lit l'adresse (`?id=`, `?new=`) pour ouvrir directement un fil.
    <Suspense>
      <ClientMessagesScreen />
    </Suspense>
  );
}
