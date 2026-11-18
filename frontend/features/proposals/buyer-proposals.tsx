"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useMe } from "@/components/auth/session";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { DetailReveal } from "@/components/motion/motion";
import { Button, ButtonLink } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { FormMessage, TextareaField } from "@/components/ui/field";
import { useDay, useMoney } from "@/features/solicitations/shared";
import { api } from "@/lib/api";
import { useAction } from "@/lib/use-action";
import { type BuyerProposal, ProposalBadge, ProposalHistory, ProposalLines, ProposalTerms } from "./shared";

const REFRESH = [["buyer-proposals"], ["purchase-requests"]];

function Details({ proposal }: { proposal: BuyerProposal }) {
  const t = useTranslations();
  const day = useDay();
  const canDecide = Boolean(useMe().data?.permissions.includes("proposal:decide"));
  const [answer, setAnswer] = useState<"refuse" | "request_changes">();
  const decide = useAction(({ action, message }: { action: string; message?: string }) => api(`/proposals/${proposal.id}/${action}`, { message }), REFRESH);
  const version = proposal.versions.at(-1)!;
  const waiting = proposal.status === "sent";

  return (
    <SectionCard title={proposal.reference} action={<ProposalBadge status={proposal.status} />}>
      <p className="mb-4 text-sm text-muted-foreground">
        {t("proposals.forRequest", { request: proposal.request_reference })} · {t("offers.version", { version: version.version })}
        {version.sent_at && ` · ${t("proposals.receivedOn", { date: day(version.sent_at) })}`}
      </p>

      {proposal.status === "changes_requested" && (
        <div className="mb-4 rounded-control bg-warning-soft px-3 py-2 text-warning-foreground">
          <p className="text-sm">{t("proposals.changesPending")}</p>
        </div>
      )}
      {proposal.status === "accepted" && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <FormMessage tone="success">{t("proposals.acceptedNotice", { version: proposal.accepted_version ?? version.version })}</FormMessage>
          <ButtonLink href="/buyer/commandes" variant="ghost" size="sm">
            {t("orders.seeOrder")}
          </ButtonLink>
        </div>
      )}

      <div className="space-y-5">
        <ProposalLines version={version} />
        <ProposalTerms version={version} />
      </div>

      {waiting && canDecide && (
        <div className="mt-6 border-t border-border pt-5">
          <h3 className="font-bold">{t("proposals.yourDecision")}</h3>
          <p className="mb-3 text-sm text-muted-foreground">{t("proposals.decisionHint", { date: day(version.valid_until) })}</p>
          <div className="flex flex-wrap gap-3">
            <Button
              disabled={decide.pending}
              onClick={() => {
                if (window.confirm(t("proposals.acceptConfirm"))) decide.run({ action: "accept" });
              }}
            >
              {t("proposals.accept")}
            </Button>
            <Button variant="outline" disabled={decide.pending} aria-expanded={answer === "request_changes"} onClick={() => setAnswer(answer === "request_changes" ? undefined : "request_changes")}>
              {t("proposals.requestChanges")}
            </Button>
            <Button variant="ghost" disabled={decide.pending} aria-expanded={answer === "refuse"} onClick={() => setAnswer(answer === "refuse" ? undefined : "refuse")}>
              {t("proposals.refuse")}
            </Button>
          </div>
          {answer && (
            <form
              key={answer}
              className="mt-4 space-y-3 rounded-control border border-border p-4"
              onSubmit={(event) => {
                event.preventDefault();
                const message = String(new FormData(event.currentTarget).get("message") ?? "").trim();
                decide.run({ action: answer, message: message || undefined }, { onSuccess: () => setAnswer(undefined) });
              }}
            >
              <TextareaField
                name="message"
                label={t(answer === "refuse" ? "proposals.refuseReason" : "proposals.changesWanted")}
                hint={t(answer === "refuse" ? "proposals.refuseHint" : "proposals.changesHint")}
                maxLength={2000}
                required={answer === "request_changes"}
              />
              <Button type="submit" disabled={decide.pending}>
                {t(answer === "refuse" ? "proposals.confirmRefuse" : "proposals.sendChanges")}
              </Button>
            </form>
          )}
        </div>
      )}
      {waiting && !canDecide && <p className="mt-5 text-sm text-muted-foreground">{t("proposals.ownerDecides")}</p>}
      {decide.errorStatus !== undefined && (
        <div className="mt-4">
          <FormMessage tone="error">{t(decide.errorStatus === 409 ? "proposals.noLongerOpen" : "common.error")}</FormMessage>
        </div>
      )}

      {proposal.versions.length > 1 && (
        <details className="mt-6 border-t border-border pt-5">
          <summary className="cursor-pointer text-sm font-semibold">{t("offers.previousVersions")}</summary>
          <div className="mt-3 space-y-5">
            {proposal.versions.slice(0, -1).reverse().map((previous) => (
              <div key={previous.version}>
                <p className="mb-2 text-sm font-semibold">
                  {t("offers.version", { version: previous.version })}
                  {previous.sent_at && ` · ${t("proposals.receivedOn", { date: day(previous.sent_at) })}`}
                </p>
                <ProposalLines version={previous} />
              </div>
            ))}
          </div>
        </details>
      )}
      <ProposalHistory events={proposal.history} />
    </SectionCard>
  );
}

/** Page acheteur « Propositions ». */
export function BuyerProposalsScreen() {
  const t = useTranslations();
  const money = useMoney();
  const day = useDay();
  const [selectedId, setSelectedId] = useState<string | undefined>(useSearchParams().get("id") ?? undefined);
  const proposals = useQuery({
    queryKey: ["buyer-proposals"],
    queryFn: () => api<BuyerProposal[]>("/proposals"),
  });
  const selected = proposals.data?.find((proposal) => proposal.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.proposals")} description={t("proposals.buyerIntro")} />
      {proposals.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {proposals.data && (
        <SectionCard title={t("nav.proposals")}>
          {proposals.data.length === 0 ? (
            <p className="text-muted-foreground">{t("proposals.emptyBuyer")}</p>
          ) : (
            <DataTable
              columns={[t("columns.reference"), t("proposals.request"), t("proposals.grandTotal"), t("proposals.validUntil"), t("columns.status"), ""]}
              rows={proposals.data.map((proposal) => {
                const current = proposal.versions.at(-1)!;
                return {
                  key: proposal.id,
                  cells: [
                    <span key="reference" className="font-semibold whitespace-nowrap">{proposal.reference}</span>,
                    <span key="request" className="whitespace-nowrap">{proposal.request_reference}</span>,
                    <span key="total" className="tabular whitespace-nowrap">{money(current.total, current.currency)}</span>,
                    day(current.valid_until),
                    <ProposalBadge key="status" status={proposal.status} />,
                    <Button
                      key="open"
                      variant="ghost"
                      size="sm"
                      aria-expanded={proposal.id === selectedId}
                      onClick={() => setSelectedId(proposal.id === selectedId ? undefined : proposal.id)}
                    >
                      {t("requests.open")}
                    </Button>,
                  ],
                };
              })}
            />
          )}
        </SectionCard>
      )}
      {selected && (
        <DetailReveal key={selected.id}>
          <Details key={`${selected.id}-${selected.status}`} proposal={selected} />
        </DetailReveal>
      )}
    </div>
  );
}
