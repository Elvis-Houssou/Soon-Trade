"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useMe } from "@/components/auth/session";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { DetailReveal } from "@/components/motion/motion";
import { Button, ButtonLink } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { FormMessage, TextareaField } from "@/components/ui/field";
import { ClaimBadge, type ClaimStatus, Facts, History, type StatusEvent } from "@/features/orders/shared";
import { useDay } from "@/features/solicitations/shared";
import { api } from "@/lib/api";
import { useAction } from "@/lib/use-action";

export type Claim = {
  id: string;
  reference: string;
  status: ClaimStatus;
  created_at: string;
  order_id: string;
  order_reference: string;
  delivery_id: string | null;
  delivery_reference: string | null;
  category: string;
  subject: string;
  description: string;
  resolution: string | null;
  history: StatusEvent[];
  /** Présent uniquement dans les réponses internes. */
  buyer_name?: string;
};

function ClaimFacts({ claim }: { claim: Claim }) {
  const t = useTranslations();
  const day = useDay();
  return (
    <Facts
      items={[
        [t("claims.category"), t(`claims.categories.${claim.category}`)],
        [t("orders.order"), claim.order_reference],
        [t("claims.delivery"), claim.delivery_reference ?? t("claims.wholeOrder")],
        [t("columns.date"), day(claim.created_at)],
        [t("claims.description"), claim.description],
      ]}
    />
  );
}

function Answer({ claim }: { claim: Claim }) {
  const t = useTranslations();
  if (!claim.resolution) return null;
  return (
    <div className={`mt-4 rounded-control px-3 py-2 ${claim.status === "rejected" ? "bg-danger-soft text-danger-foreground" : "bg-success-soft text-success-foreground"}`}>
      <p className="text-sm font-semibold">{t("claims.answer")}</p>
      <p className="whitespace-pre-line">{claim.resolution}</p>
    </div>
  );
}

function ClaimList({ claims, selectedId, onSelect, internal = false }: { claims: Claim[]; selectedId?: string; onSelect: (id?: string) => void; internal?: boolean }) {
  const t = useTranslations();
  const day = useDay();
  return (
    <DataTable
      columns={[t("columns.reference"), ...(internal ? [t("proposals.buyer")] : []), t("claims.subject"), t("orders.order"), t("columns.date"), t("columns.status"), ""]}
      rows={claims.map((claim) => ({
        key: claim.id,
        cells: [
          <span key="reference" className="font-semibold whitespace-nowrap">{claim.reference}</span>,
          ...(internal ? [claim.buyer_name ?? ""] : []),
          claim.subject,
          <span key="order" className="whitespace-nowrap">{claim.order_reference}</span>,
          day(claim.created_at),
          <ClaimBadge key="status" status={claim.status} />,
          <Button key="open" variant="ghost" size="sm" aria-expanded={claim.id === selectedId} onClick={() => onSelect(claim.id === selectedId ? undefined : claim.id)}>
            {t("requests.open")}
          </Button>,
        ],
      }))}
    />
  );
}

/** Page acheteur « Réclamations ». Une réclamation s'ouvre depuis la commande concernée. */
export function BuyerClaimsScreen() {
  const t = useTranslations();
  const [selectedId, setSelectedId] = useState<string>();
  const claims = useQuery({ queryKey: ["buyer-claims"], queryFn: () => api<Claim[]>("/claims") });
  const close = useAction((id: string) => api(`/claims/${id}/close`, {}), [["buyer-claims"]]);
  const selected = claims.data?.find((claim) => claim.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.claims")} description={t("claims.buyerIntro")} />
      {claims.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {claims.data && (
        <SectionCard
          title={t("nav.claims")}
          action={
            <ButtonLink href="/buyer/commandes" variant="ghost" size="sm">
              {t("nav.orders")}
            </ButtonLink>
          }
        >
          {claims.data.length === 0 ? (
            <p className="text-muted-foreground">{t("claims.emptyBuyer")}</p>
          ) : (
            <ClaimList claims={claims.data} selectedId={selectedId} onSelect={setSelectedId} />
          )}
        </SectionCard>
      )}
      {selected && (
        <DetailReveal key={selected.id}>
          <SectionCard title={`${selected.reference} · ${selected.subject}`} action={<ClaimBadge status={selected.status} />}>
            <ClaimFacts claim={selected} />
            <Answer claim={selected} />
            {["resolved", "rejected"].includes(selected.status) && (
              <div className="mt-4">
                <Button variant="outline" disabled={close.pending} onClick={() => close.run(selected.id)}>
                  {t("claims.closeMine")}
                </Button>
              </div>
            )}
            <History events={selected.history} badge={(value) => <ClaimBadge status={value as ClaimStatus} />} />
          </SectionCard>
        </DetailReveal>
      )}
    </div>
  );
}

function InternalDetails({ claim }: { claim: Claim }) {
  const t = useTranslations();
  const me = useMe().data;
  const [answering, setAnswering] = useState<"resolve" | "reject">();
  const act = useAction(({ action, message }: { action: string; message?: string }) => api(`/internal/claims/${claim.id}/${action}`, { message }), [["internal-claims"], ["internal-orders"]]);
  const can = (permission: string) => Boolean(me?.permissions.includes(permission));

  return (
    <SectionCard title={`${claim.reference} · ${claim.buyer_name}`} action={<ClaimBadge status={claim.status} />}>
      <p className="mb-3 font-semibold">{claim.subject}</p>
      <ClaimFacts claim={claim} />
      <Answer claim={claim} />
      <div className="mt-5 flex flex-wrap gap-3">
        {claim.status === "open" && can("claim:handle") && (
          <Button disabled={act.pending} onClick={() => act.run({ action: "review" })}>
            {t("claims.actions.review")}
          </Button>
        )}
        {claim.status === "under_review" && can("claim:decide") && (
          <>
            <Button aria-expanded={answering === "resolve"} onClick={() => setAnswering(answering === "resolve" ? undefined : "resolve")}>
              {t("claims.actions.resolve")}
            </Button>
            <Button variant="outline" aria-expanded={answering === "reject"} onClick={() => setAnswering(answering === "reject" ? undefined : "reject")}>
              {t("claims.actions.reject")}
            </Button>
          </>
        )}
        {["resolved", "rejected"].includes(claim.status) && can("claim:decide") && (
          <Button variant="ghost" disabled={act.pending} onClick={() => act.run({ action: "close" })}>
            {t("claims.actions.close")}
          </Button>
        )}
        <ButtonLink href={`/internal/commandes?id=${claim.order_id}`} variant="ghost">
          {t("orders.openOrder")}
        </ButtonLink>
      </div>
      {answering && (
        <form
          key={answering}
          className="mt-4 space-y-3 rounded-control border border-border p-4"
          onSubmit={(event) => {
            event.preventDefault();
            const message = String(new FormData(event.currentTarget).get("message") ?? "").trim();
            act.run({ action: answering, message }, { onSuccess: () => setAnswering(undefined) });
          }}
        >
          <TextareaField name="message" label={t("claims.answer")} hint={t("claims.answerHint")} maxLength={2000} required />
          <Button type="submit" disabled={act.pending}>
            {t(`claims.actions.${answering}`)}
          </Button>
        </form>
      )}
      {act.errorStatus !== undefined && (
        <div className="mt-3">
          <FormMessage tone="error">{t(act.errorStatus === 409 ? "orders.conflict" : "common.error")}</FormMessage>
        </div>
      )}
      <History events={claim.history} badge={(value) => <ClaimBadge status={value as ClaimStatus} />} />
    </SectionCard>
  );
}

/** Page interne « Réclamations ». */
export function InternalClaimsScreen() {
  const t = useTranslations();
  const [selectedId, setSelectedId] = useState<string>();
  const claims = useQuery({ queryKey: ["internal-claims"], queryFn: () => api<Claim[]>("/internal/claims") });
  const selected = claims.data?.find((claim) => claim.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.claims")} description={t("claims.internalIntro")} />
      {claims.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {claims.data && (
        <SectionCard title={t("nav.claims")}>
          {claims.data.length === 0 ? (
            <p className="text-muted-foreground">{t("claims.emptyInternal")}</p>
          ) : (
            <ClaimList claims={claims.data} selectedId={selectedId} onSelect={setSelectedId} internal />
          )}
        </SectionCard>
      )}
      {selected && (
        <DetailReveal key={selected.id}>
          <InternalDetails key={`${selected.id}-${selected.status}`} claim={selected} />
        </DetailReveal>
      )}
    </div>
  );
}
