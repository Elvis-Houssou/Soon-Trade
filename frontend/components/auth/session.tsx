"use client";

import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useState } from "react";
import type { SpaceId } from "@/features/navigation/spaces";
import { useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api";

export type Me = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  /** Langue des e-mails, alignée sur la langue affichée (voir AppShell). */
  locale: string;
  organization: { id: string; name: string; kind: SpaceId };
  permissions: string[];
};

export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 60_000 } } }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/auth/me") });
}

/** À appeler après une connexion réussie : mémorise l'utilisateur et ouvre son espace. */
export function useEnterSpace() {
  const queryClient = useQueryClient();
  const router = useRouter();
  return (me: Me) => {
    queryClient.setQueryData(["me"], me);
    router.replace(`/${me.organization.kind}`);
  };
}

export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();
  return async () => {
    await api("/auth/logout", undefined, "POST").catch(() => undefined);
    queryClient.clear();
    router.replace("/connexion");
  };
}

/**
 * Confort d'interface uniquement : renvoie à la connexion ou vers le bon espace.
 * La vraie protection est côté API, qui vérifie session, rôle et organisation.
 */
export function useSpaceGuard(spaceId: SpaceId) {
  const me = useMe();
  const router = useRouter();
  const unauthenticated = me.error instanceof ApiError && me.error.status === 401;
  const elsewhere = me.data && me.data.organization.kind !== spaceId ? me.data.organization.kind : undefined;

  useEffect(() => {
    if (unauthenticated) router.replace("/connexion");
    else if (elsewhere) router.replace(`/${elsewhere}`);
  }, [unauthenticated, elsewhere, router]);

  return {
    me: elsewhere ? undefined : me.data,
    failed: Boolean(me.error) && !unauthenticated,
  };
}
