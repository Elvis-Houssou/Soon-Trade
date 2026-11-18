"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";

/**
 * Action d'écriture vers l'API : rafraîchit les listes concernées en cas de succès et
 * expose le statut HTTP de l'erreur pour choisir un message traduit.
 */
export function useAction<V = void>(run: (variables: V) => Promise<unknown>, refresh: string[][] = []) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: run,
    onSuccess: () => Promise.all(refresh.map((queryKey) => queryClient.invalidateQueries({ queryKey }))),
  });
  return {
    run: mutation.mutate,
    pending: mutation.isPending,
    done: mutation.isSuccess,
    /** 0 = réseau injoignable ; undefined = pas d'erreur. */
    errorStatus: mutation.error ? (mutation.error instanceof ApiError ? mutation.error.status : 0) : undefined,
    reset: mutation.reset,
  };
}

/** Lit un formulaire en objet, en retirant les champs laissés vides. */
export function formValues(form: HTMLFormElement) {
  const entries = [...new FormData(form)].map(([key, value]) => [key, String(value).trim()] as const);
  return Object.fromEntries(entries);
}
