import { Suspense } from "react";
import { InternalMessagesScreen } from "@/features/messaging/messages";

export default function Page() {
  return (
    // L'écran lit l'adresse (`?id=`, `?new=`) pour ouvrir directement un fil.
    <Suspense>
      <InternalMessagesScreen />
    </Suspense>
  );
}
