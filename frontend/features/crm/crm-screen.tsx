"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { useMe } from "@/components/auth/session";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { DetailReveal } from "@/components/motion/motion";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { FormMessage, TextareaField } from "@/components/ui/field";
import { api } from "@/lib/api";
import { useAction } from "@/lib/use-action";

type Client = {
  id: string;
  name: string;
  kind: "buyer" | "supplier";
  city: string | null;
  verification_status: string;
  last_activity: string | null;
  requests: number;
  orders: number;
  open_claims: number;
  conversations: number;
};

type Entry = { at: string; kind: string; reference: string; status: string | null; label: string; link: string | null; author: string | null };
type ClientFile = Client & { timeline: Entry[] };

/** Statut d'un objet de la chronologie, dans le vocabulaire de son propre écran. */
const STATUS_NAMESPACE: Record<string, string> = {
  request: "requestStatus",
  proposal: "proposalStatus",
  order: "orderStatus",
  supplier_order: "orderStatus",
  claim: "claimStatus",
  solicitation: "solicitationStatus",
  offer: "offerStatus",
};

function Timeline({ entries }: { entries: Entry[] }) {
  const t = useTranslations();
  const format = useFormatter();
  if (entries.length === 0) return <p className="text-muted-foreground">{t("crm.noActivity")}</p>;
  return (
    <ol className="relative space-y-4 border-l border-border pl-5">
      {entries.map((entry, index) => {
        const namespace = STATUS_NAMESPACE[entry.kind];
        const status = entry.status && namespace && t.has(`${namespace}.${entry.status}`) ? t(`${namespace}.${entry.status}`) : entry.status;
        return (
          <li key={index} className="relative">
            <span aria-hidden className="absolute -left-[1.6rem] top-1.5 size-2.5 rounded-full border-2 border-surface bg-primary" />
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
              <span className="font-semibold">{t(`crm.kinds.${entry.kind}`)}</span>
              {entry.reference && <span className="text-muted-foreground">{entry.reference}</span>}
              {status && entry.kind === "conversation" ? <Badge>{t(`messages.${entry.status}`)}</Badge> : status && <Badge>{status}</Badge>}
              <span className="text-muted-foreground">· {format.dateTime(new Date(entry.at), { dateStyle: "medium", timeStyle: "short" })}</span>
              {entry.author && <span className="text-muted-foreground">· {entry.author}</span>}
            </p>
            <p className={entry.kind === "note" ? "mt-1 whitespace-pre-line rounded-control bg-surface-muted px-3 py-2" : "mt-0.5"}>
              {entry.label}
              {entry.link && (
                <ButtonLink href={`/${entry.link}`} variant="ghost" size="sm" className="ml-1">
                  {t("crm.open")}
                </ButtonLink>
              )}
            </p>
          </li>
        );
      })}
    </ol>
  );
}

function ClientDetails({ id }: { id: string }) {
  const t = useTranslations();
  const canNote = Boolean(useMe().data?.permissions.includes("crm:note"));
  const file = useQuery({ queryKey: ["crm-file", id], queryFn: () => api<ClientFile>(`/internal/crm/${id}`) });
  const note = useAction((body: string) => api(`/internal/crm/${id}/notes`, { body }), [["crm-file", id], ["crm-clients"]]);
  if (!file.data) return null;
  const client = file.data;

  return (
    <SectionCard
      title={client.name}
      action={
        <ButtonLink href={`/internal/messages?new=${client.id}`} variant="ghost" size="sm">
          {t("crm.write")}
        </ButtonLink>
      }
    >
      <p className="mb-5 text-sm text-muted-foreground">
        {t(`messages.kinds.${client.kind}`)}
        {client.city && ` · ${client.city}`}
      </p>
      {canNote && (
        <form
          className="mb-6 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            note.run(String(new FormData(form).get("body") ?? "").trim(), { onSuccess: () => form.reset() });
          }}
        >
          <TextareaField name="body" label={t("crm.note")} hint={t("crm.noteHint")} maxLength={4000} required />
          <Button type="submit" variant="outline" disabled={note.pending}>
            {t("crm.addNote")}
          </Button>
          {note.errorStatus !== undefined && <FormMessage tone="error">{t("common.error")}</FormMessage>}
        </form>
      )}
      <h3 className="mb-3 font-bold">{t("crm.history")}</h3>
      <Timeline entries={client.timeline} />
    </SectionCard>
  );
}

/** Page interne « CRM » : chaque client et l'historique de la relation. */
export function CrmScreen() {
  const t = useTranslations();
  const format = useFormatter();
  const [selectedId, setSelectedId] = useState<string>();
  const clients = useQuery({ queryKey: ["crm-clients"], queryFn: () => api<Client[]>("/internal/crm") });

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.crm")} description={t("crm.intro")} />
      {clients.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {clients.data && (
        <SectionCard title={t("crm.clients")}>
          <DataTable
            columns={[t("crm.client"), t("crm.type"), t("crm.requests"), t("nav.orders"), t("crm.openClaims"), t("crm.lastActivity"), ""]}
            rows={clients.data.map((client) => ({
              key: client.id,
              cells: [
                <span key="name" className="font-semibold">{client.name}</span>,
                t(`messages.kinds.${client.kind}`),
                <span key="requests" className="tabular">{client.requests}</span>,
                <span key="orders" className="tabular">{client.orders}</span>,
                <span key="claims" className="tabular">{client.open_claims}</span>,
                client.last_activity ? format.relativeTime(new Date(client.last_activity)) : "—",
                <Button key="open" variant="ghost" size="sm" aria-expanded={client.id === selectedId} onClick={() => setSelectedId(client.id === selectedId ? undefined : client.id)}>
                  {t("crm.open")}
                </Button>,
              ],
            }))}
          />
        </SectionCard>
      )}
      {selectedId && (
        <DetailReveal key={selectedId}>
          <ClientDetails id={selectedId} />
        </DetailReveal>
      )}
    </div>
  );
}
