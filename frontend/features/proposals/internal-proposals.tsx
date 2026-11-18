"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { useMe } from "@/components/auth/session";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { DetailReveal } from "@/components/motion/motion";
import { Button, ButtonLink } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage, SelectField, TextareaField } from "@/components/ui/field";
import { useQuantity } from "@/features/requests/shared";
import { type InternalSolicitation, useDay, useMoney } from "@/features/solicitations/shared";
import { api } from "@/lib/api";
import { useAction } from "@/lib/use-action";
import { cn } from "@/lib/utils";
import { type InternalProposal, type InternalVersion, ProposalBadge, ProposalHistory, ProposalTerms } from "./shared";

const UNITS = ["kg", "tonne", "litre", "sac", "carton", "unite"];
const REFRESH = [["internal-proposals"]];

type LineDraft = {
  product_name: string;
  quantity: string;
  unit: string;
  unit_price: string;
  offer_id: string | null;
  supplier_name: string | null;
  supplier_unit_price: string | null;
};

function amount(value: string) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

/** Message d'erreur selon le refus de l'API : 400 règle métier, 403 quatre yeux, 409 état changé. */
function useRefusal() {
  const t = useTranslations();
  return (status: number) =>
    t(status === 400 ? "proposals.refused400" : status === 403 ? "proposals.fourEyes" : status === 409 ? "requests.conflict" : "common.error");
}

/** Préparation de la version en cours : prix de vente, conditions, mot à l'acheteur. */
function Editor({ proposal, version }: { proposal: InternalProposal; version: InternalVersion }) {
  const t = useTranslations();
  const format = useFormatter();
  const money = useMoney();
  const refusal = useRefusal();
  const [lines, setLines] = useState<LineDraft[]>(version.lines.map((line) => ({ ...line })));
  const solicitations = useQuery({
    queryKey: ["case-solicitations", proposal.case_id],
    queryFn: () => api<InternalSolicitation[]>(`/sourcing/cases/${proposal.case_id}/solicitations`),
  });
  const unused = (solicitations.data ?? []).filter(
    (solicitation) => solicitation.offer?.status === "retained" && !lines.some((line) => line.offer_id === solicitation.offer?.id),
  );
  const save = useAction(async ({ body, submit }: { body: object; submit: boolean }) => {
    await api(`/internal/proposals/${proposal.id}`, body, "PUT");
    if (submit) await api(`/internal/proposals/${proposal.id}/submit`, {});
  }, REFRESH);

  const update = (index: number, changes: Partial<LineDraft>) =>
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...changes } : line)));
  const total = lines.reduce((sum, line) => sum + amount(line.unit_price) * amount(line.quantity), 0);
  const cost = lines.reduce((sum, line) => sum + (line.supplier_unit_price ? amount(line.supplier_unit_price) * amount(line.quantity) : 0), 0);
  const currency = version.currency;

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const submit = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "submit";
        const text = (name: string) => String(form.get(name) ?? "").trim() || null;
        save.run({
          submit,
          body: {
            lead_time_days: Number(form.get("lead_time_days")),
            valid_until: text("valid_until"),
            delivery_location: text("delivery_location"),
            conditions: text("conditions"),
            message: text("message"),
            lines: lines.map(({ product_name, quantity, unit, unit_price, offer_id }) => ({ product_name, quantity, unit, unit_price, offer_id })),
          },
        });
      }}
    >
      <p className="text-sm text-muted-foreground">{t(version.version === 1 ? "proposals.editorHint" : "proposals.editorHintRevision")}</p>
      <ol className="space-y-3">
        {lines.map((line, index) => {
          const lineTotal = amount(line.unit_price) * amount(line.quantity);
          const lineMargin = line.supplier_unit_price ? lineTotal - amount(line.supplier_unit_price) * amount(line.quantity) : null;
          return (
            <li key={index} className="rounded-control border border-border p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="text-muted-foreground">
                  {line.supplier_name ? t("proposals.fromOffer", { supplier: line.supplier_name }) : t("proposals.freeLine")}
                  {line.supplier_unit_price && ` · ${t("proposals.cost")} ${money(line.supplier_unit_price, currency)}`}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={t("proposals.removeLine")}
                  disabled={lines.length === 1}
                  onClick={() => setLines((current) => current.filter((_, i) => i !== index))}
                >
                  <Trash2 className="size-4" aria-hidden />
                </Button>
              </div>
              <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_1fr]">
                <Field label={t("requests.product")} value={line.product_name} onChange={(e) => update(index, { product_name: e.target.value })} minLength={2} maxLength={200} required />
                <Field label={t("requests.quantity")} type="number" min={0.001} step="0.001" value={line.quantity} onChange={(e) => update(index, { quantity: e.target.value })} required />
                <SelectField label={t("requests.unit")} value={line.unit} onChange={(e) => update(index, { unit: e.target.value })}>
                  {UNITS.map((unit) => (
                    <option key={unit} value={unit}>
                      {t(`units.${unit}`)}
                    </option>
                  ))}
                </SelectField>
                <Field label={t("proposals.salePrice")} type="number" min={0.01} step="0.01" value={line.unit_price} onChange={(e) => update(index, { unit_price: e.target.value })} required />
              </div>
              <p className="mt-2 flex flex-wrap justify-end gap-x-4 text-sm">
                <span>
                  {t("offers.total")} <span className="tabular font-semibold">{money(String(lineTotal), currency)}</span>
                </span>
                {lineMargin !== null && (
                  <span className={cn(lineMargin < 0 && "text-danger-foreground")}>
                    {t("proposals.margin")} <span className="tabular font-semibold">{money(String(lineMargin), currency)}</span>
                  </span>
                )}
              </p>
            </li>
          );
        })}
      </ol>
      <div className="flex flex-wrap items-end gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setLines((current) => [...current, { product_name: "", quantity: "1", unit: "unite", unit_price: "", offer_id: null, supplier_name: null, supplier_unit_price: null }])}
        >
          <Plus className="size-4" aria-hidden />
          {t("proposals.addLine")}
        </Button>
        {unused.length > 0 && (
          <SelectField
            label={t("proposals.addFromOffer")}
            className="sm:w-72"
            value=""
            onChange={(event) => {
              const solicitation = unused.find((s) => s.offer?.id === event.target.value);
              const current = solicitation?.offer?.versions.at(-1);
              if (!solicitation?.offer || !current) return;
              setLines((existing) => [
                ...existing,
                {
                  product_name: solicitation.product_name,
                  quantity: current.quantity,
                  unit: solicitation.unit,
                  unit_price: current.unit_price,
                  offer_id: solicitation.offer!.id,
                  supplier_name: solicitation.supplier_name,
                  supplier_unit_price: current.unit_price,
                },
              ]);
            }}
          >
            <option value="">—</option>
            {unused.map((solicitation) => (
              <option key={solicitation.offer!.id} value={solicitation.offer!.id}>
                {solicitation.supplier_name} · {solicitation.offer!.reference}
              </option>
            ))}
          </SelectField>
        )}
      </div>

      <div className="grid gap-3 rounded-control bg-surface-muted p-4 sm:grid-cols-3">
        <p>
          <span className="block text-sm text-muted-foreground">{t("proposals.grandTotal")}</span>
          <span className="tabular font-display text-lg font-extrabold">{money(String(total), currency)}</span>
        </p>
        <p>
          <span className="block text-sm text-muted-foreground">{t("proposals.costTotal")}</span>
          <span className="tabular font-semibold">{money(String(cost), currency)}</span>
        </p>
        <p className={cn(total - cost < 0 && "text-danger-foreground")}>
          <span className="block text-sm text-muted-foreground">{t("proposals.margin")}</span>
          <span className="tabular font-semibold">
            {money(String(total - cost), currency)}
            {cost > 0 && ` · ${format.number((total - cost) / cost, { style: "percent", maximumFractionDigits: 1 })}`}
          </span>
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field name="lead_time_days" label={t("offers.leadTime")} hint={t("proposals.daysHint")} type="number" min={0} max={365} defaultValue={version.lead_time_days} required />
        <Field name="valid_until" label={t("proposals.validUntil")} hint={t("proposals.validityHint")} type="date" defaultValue={version.valid_until} required />
        <Field name="delivery_location" label={t("requests.deliveryLocation")} defaultValue={version.delivery_location} minLength={2} maxLength={300} required />
      </div>
      <TextareaField name="conditions" label={t("offers.conditions")} hint={t("proposals.conditionsHint")} defaultValue={version.conditions ?? ""} maxLength={4000} />
      <TextareaField name="message" label={t("proposals.message")} hint={t("proposals.messageHint")} defaultValue={version.message ?? ""} maxLength={2000} />
      {save.errorStatus !== undefined && <FormMessage tone="error">{refusal(save.errorStatus)}</FormMessage>}
      {save.done && <FormMessage tone="success">{t("proposals.saved")}</FormMessage>}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" value="submit" disabled={save.pending}>
          {t("proposals.submit")}
        </Button>
        <Button type="submit" value="save" variant="outline" disabled={save.pending}>
          {t("common.save")}
        </Button>
      </div>
    </form>
  );
}

/** Lecture interne d'une version : prix de vente, prix d'achat et marge par ligne. */
function InternalLines({ version }: { version: InternalVersion }) {
  const t = useTranslations();
  const money = useMoney();
  const quantity = useQuantity();
  return (
    <div>
      <DataTable
        columns={[t("columns.product"), t("columns.quantity"), t("proposals.salePrice"), t("offers.total"), t("sourcing.supplier"), t("proposals.cost")]}
        rows={version.lines.map((line, index) => ({
          key: String(index),
          cells: [
            <span key="product" className="font-medium">{line.product_name}</span>,
            <span key="quantity" className="tabular whitespace-nowrap">{quantity(line)}</span>,
            <span key="price" className="tabular whitespace-nowrap">{money(line.unit_price, version.currency)}</span>,
            <span key="total" className="tabular whitespace-nowrap">{money(line.total, version.currency)}</span>,
            line.supplier_name ? (
              <span key="supplier">
                {line.supplier_name}
                <span className="block text-sm text-muted-foreground">{line.offer_reference}</span>
              </span>
            ) : (
              t("proposals.freeLine")
            ),
            <span key="cost" className="tabular whitespace-nowrap">{line.supplier_unit_price ? money(line.supplier_unit_price, version.currency) : "—"}</span>,
          ],
        }))}
      />
      <p className="mt-3 flex flex-wrap items-baseline justify-end gap-x-6 gap-y-1 border-t border-border pt-3 text-sm">
        <span>
          {t("proposals.costTotal")} <span className="tabular font-semibold">{money(version.cost_total, version.currency)}</span>
        </span>
        <span className={cn(Number(version.margin) < 0 && "text-danger-foreground")}>
          {t("proposals.margin")} <span className="tabular font-semibold">{money(version.margin, version.currency)}</span>
        </span>
        <span>
          {t("proposals.grandTotal")} <span className="tabular font-display text-lg font-extrabold">{money(version.total, version.currency)}</span>
        </span>
      </p>
    </div>
  );
}

function Details({ proposal }: { proposal: InternalProposal }) {
  const t = useTranslations();
  const day = useDay();
  const me = useMe().data;
  const refusal = useRefusal();
  const [returning, setReturning] = useState(false);
  const can = (permission: string) => Boolean(me?.permissions.includes(permission));
  const act = useAction(({ path, message }: { path: string; message?: string }) => api(`/internal/proposals/${proposal.id}/${path}`, { message }), REFRESH);
  const version = proposal.versions.at(-1)!;
  const status = proposal.status;
  const ownSubmission = proposal.submitted_by?.id === me?.id;
  // La demande de l'acheteur reste sous les yeux tant que la version qui y répond n'est pas partie.
  const lastRequest = [...proposal.events].reverse().find((event) => event.to_status === "changes_requested");
  const lastBuyerMessage =
    lastRequest && (status === "changes_requested" || (["draft", "pending_validation"].includes(status) && lastRequest.version === version.version - 1))
      ? lastRequest.message
      : null;

  return (
    <SectionCard title={`${proposal.reference} · ${proposal.buyer_name}`} action={<ProposalBadge status={status} />}>
      <p className="mb-4 text-sm text-muted-foreground">
        {t("proposals.basedOn", { request: proposal.request_reference, case: proposal.case_reference })} · {t("offers.version", { version: version.version })}
        {version.sent_at && ` · ${t("proposals.sentOn", { date: day(version.sent_at) })}`}
      </p>

      {lastBuyerMessage && (
        <div className="mb-4 rounded-control bg-warning-soft px-3 py-2 text-warning-foreground">
          <p className="text-sm font-semibold">{t("proposals.buyerAsks")}</p>
          <p className="whitespace-pre-line">{lastBuyerMessage}</p>
        </div>
      )}
      {status === "pending_validation" && (
        <div className="mb-4 rounded-control bg-primary-soft px-3 py-2 text-primary-soft-foreground">
          <p className="text-sm">{t("proposals.pendingHint", { name: proposal.submitted_by?.full_name ?? "" })}</p>
        </div>
      )}

      {status === "draft" && can("proposal:manage") ? (
        <Editor key={version.version} proposal={proposal} version={version} />
      ) : (
        <div className="space-y-5">
          <InternalLines version={version} />
          <ProposalTerms version={version} />
        </div>
      )}

      {act.errorStatus !== undefined && (
        <div className="mt-4">
          <FormMessage tone="error">{refusal(act.errorStatus)}</FormMessage>
        </div>
      )}
      <div className="mt-5 flex flex-wrap gap-3">
        {status === "pending_validation" && can("proposal:validate") && (
          <>
            <Button
              disabled={act.pending || ownSubmission}
              title={ownSubmission ? t("proposals.fourEyes") : undefined}
              onClick={() => {
                if (window.confirm(t("proposals.sendConfirm", { buyer: proposal.buyer_name }))) act.run({ path: "validation/send" });
              }}
            >
              {t("proposals.validateAndSend")}
            </Button>
            <Button variant="outline" disabled={act.pending} onClick={() => setReturning((open) => !open)} aria-expanded={returning}>
              {t("proposals.return")}
            </Button>
          </>
        )}
        {["changes_requested", "expired"].includes(status) && can("proposal:manage") && (
          <Button disabled={act.pending} onClick={() => act.run({ path: "revise" })}>
            {t("proposals.revise")}
          </Button>
        )}
        {["draft", "pending_validation", "changes_requested"].includes(status) && can("proposal:manage") && (
          <Button
            variant="ghost"
            disabled={act.pending}
            onClick={() => {
              if (window.confirm(t("proposals.cancelConfirm"))) act.run({ path: "cancel" });
            }}
          >
            {t("proposals.cancel")}
          </Button>
        )}
      </div>
      {ownSubmission && status === "pending_validation" && can("proposal:validate") && (
        <p className="mt-2 text-sm text-muted-foreground">{t("proposals.fourEyes")}</p>
      )}
      {returning && status === "pending_validation" && (
        <form
          className="mt-4 space-y-3 rounded-control border border-border p-4"
          onSubmit={(event) => {
            event.preventDefault();
            const message = String(new FormData(event.currentTarget).get("message") ?? "").trim();
            act.run({ path: "validation/return", message: message || undefined }, { onSuccess: () => setReturning(false) });
          }}
        >
          <TextareaField name="message" label={t("proposals.returnReason")} hint={t("proposals.returnHint")} maxLength={2000} required />
          <Button type="submit" disabled={act.pending}>
            {t("proposals.return")}
          </Button>
        </form>
      )}

      {proposal.versions.length > 1 && (
        <details className="mt-6 border-t border-border pt-5">
          <summary className="cursor-pointer text-sm font-semibold">{t("offers.previousVersions")}</summary>
          <div className="mt-3 space-y-5">
            {proposal.versions.slice(0, -1).reverse().map((previous) => (
              <div key={previous.version}>
                <p className="mb-2 text-sm font-semibold">
                  {t("offers.version", { version: previous.version })}
                  {previous.sent_at && ` · ${t("proposals.sentOn", { date: day(previous.sent_at) })}`}
                </p>
                <InternalLines version={previous} />
              </div>
            ))}
          </div>
        </details>
      )}
      <ProposalHistory events={proposal.events} />
    </SectionCard>
  );
}

/** Section « Proposition à l'acheteur » d'un dossier de sourcing. */
export function CaseProposal({ caseId, active }: { caseId: string; active: boolean }) {
  const t = useTranslations();
  const me = useMe().data;
  const canRead = Boolean(me?.permissions.includes("proposal:read"));
  const canManage = Boolean(me?.permissions.includes("proposal:manage"));
  const proposals = useQuery({
    queryKey: ["internal-proposals"],
    queryFn: () => api<InternalProposal[]>("/internal/proposals"),
    enabled: canRead,
  });
  const create = useAction(() => api(`/sourcing/cases/${caseId}/proposal`, {}), REFRESH);
  if (!canRead) return null;
  const proposal = proposals.data?.find((p) => p.case_id === caseId && p.status !== "cancelled");

  return (
    <div className="mt-6 border-t border-border pt-5">
      <h3 className="font-bold">{t("proposals.caseTitle")}</h3>
      <p className="mb-3 text-sm text-muted-foreground">{t("proposals.caseHint")}</p>
      {proposal ? (
        <p className="flex flex-wrap items-center gap-3">
          <span className="font-semibold">{proposal.reference}</span>
          <ProposalBadge status={proposal.status} />
          <ButtonLink href={`/internal/propositions?id=${proposal.id}`} variant="ghost" size="sm">
            {t("proposals.open")}
          </ButtonLink>
        </p>
      ) : canManage && active ? (
        <Button size="sm" disabled={create.pending} onClick={() => create.run()}>
          {t("proposals.prepare")}
        </Button>
      ) : (
        <p className="text-muted-foreground">{t("proposals.noneForCase")}</p>
      )}
      {create.errorStatus !== undefined && (
        <div className="mt-3">
          <FormMessage tone="error">{t(create.errorStatus === 400 ? "proposals.needRetained" : "requests.conflict")}</FormMessage>
        </div>
      )}
    </div>
  );
}

/** Page interne « Propositions acheteurs ». */
export function InternalProposalsScreen() {
  const t = useTranslations();
  const money = useMoney();
  const day = useDay();
  const [selectedId, setSelectedId] = useState<string | undefined>(useSearchParams().get("id") ?? undefined);
  const proposals = useQuery({
    queryKey: ["internal-proposals"],
    queryFn: () => api<InternalProposal[]>("/internal/proposals"),
  });
  const selected = proposals.data?.find((proposal) => proposal.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.buyerProposals")} description={t("proposals.internalIntro")} />
      {proposals.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {proposals.data && (
        <SectionCard
          title={t("nav.buyerProposals")}
          action={
            <ButtonLink href="/internal/sourcing" variant="ghost" size="sm">
              {t("requests.goToSourcing")}
            </ButtonLink>
          }
        >
          {proposals.data.length === 0 ? (
            <p className="text-muted-foreground">{t("proposals.emptyInternal")}</p>
          ) : (
            <DataTable
              columns={[t("columns.reference"), t("proposals.buyer"), t("proposals.request"), t("proposals.grandTotal"), t("proposals.validUntil"), t("columns.status"), ""]}
              rows={proposals.data.map((proposal) => {
                const current = proposal.versions.at(-1)!;
                return {
                  key: proposal.id,
                  cells: [
                    <span key="reference" className="font-semibold whitespace-nowrap">{proposal.reference}</span>,
                    proposal.buyer_name,
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
          <Details key={`${selected.id}-${selected.status}-${selected.versions.length}`} proposal={selected} />
        </DetailReveal>
      )}
    </div>
  );
}
