"use client";

import { useSyncExternalStore } from "react";

// Pendant la génération de la page, l'année du build (Next.js refuse d'y lire la date) ;
// dans le navigateur, l'année courante.
const BUILD_YEAR = 2026;
const subscribe = () => () => {};

export function CurrentYear() {
  return <>{useSyncExternalStore(subscribe, () => new Date().getFullYear(), () => BUILD_YEAR)}</>;
}
