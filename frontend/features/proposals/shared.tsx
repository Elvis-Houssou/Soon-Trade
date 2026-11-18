"use client";

import { useFormatter, useTranslations } from "next-intl";
import { DataTable } from "@/components/dashboard/widgets";
import { Badge, type Tone } from "@/components/ui/badge";
import { useQuantity } from "@/features/requests/shared";
import { useDay, useMoney } from "@/features/solicitations/shared";

export type ProposalStatus =
  | "draft"
  | "pending_validation"
  | "sent"
  | "changes_requested"
  | "accepted"
  | "refused"
  | "expired"
  | "cancelled";

export type ProposalLine = {
  product_name: string;
  quantity: string;
  unit: string;
  unit_price: string;
  total: string;
};

export type ProposalVersion = {
  version: number;
  sent_at: string | null;
  currency: string;
  lead_time_days: number;
  valid_until: string;
  delivery_location: string;
  conditions: string | null;
  message: string | null;
  total: string;
  lines: ProposalLine[];
};

export type ProposalEvent = {
  created_at: string;
  to_status: ProposalStatus;
  version: number;
  message: string | null;
};

/** Ce que reçoit l'acheteur : ni fournisseur, ni prix d'achat, ni marge. */
export type BuyerProposal = {
  id: string;
  reference: string;
  status: ProposalStatus;
  request_id: string;
  request_reference: string;
  accepted_version: number | null;
  versions: ProposalVersion[];
  history: ProposalEvent[];
};

export type InternalLine = ProposalLine & {
  offer_id: string | null;
  offer_reference: string | null;
  supplier_name: string | null;
  supplier_unit_price: string | null;
  cost_total: string;
};

export type InternalVersion = Omit<ProposalVersion, "lines"> & {
  created_at: string;
  cost_total: string;
  margin: string;
  lines: InternalLine[];
};

export type InternalProposal = {
  id: string;
  reference: string;
  status: ProposalStatus;
  created_at: string;
  case_id: string;
  case_reference: string;
  request_id: string;
  request_reference: string;
  buyer_name: string;
  created_by: { id: string; full_name: string };
  submitted_by: { id: string; full_name: string } | null;
  accepted_version: number | null;
  versions: InternalVersion[];
  events: (ProposalEvent & { from_status: ProposalStatus | null; actor_name: string })[];
};

const TONE: Record<ProposalStatus, Tone> = {
  draft: "neutral",
  pending_validation: "warning",
  sent: "primary",
  changes_requested: "warning",
  accepted: "success",
  refused: "danger",
  expired: "neutral",
  cancelled: "neutral",
};

export function ProposalBadge({ status }: { status: ProposalStatus }) {
  const t = useTranslations("proposalStatus");
  return <Badge tone={TONE[status]}>{t(status)}</Badge>;
}

/** Lignes et total d'une version, telles que l'acheteur les lit. */
export function ProposalLines({ version }: { version: ProposalVersion }) {
  const t = useTranslations();
  const money = useMoney();
  const quantity = useQuantity();
  return (
    <div>
      <DataTable
        columns={[t("columns.product"), t("columns.quantity"), t("offers.unitPrice"), t("offers.total")]}
        rows={version.lines.map((line, index) => ({
          key: String(index),
          cells: [
            <span key="product" className="font-medium">{line.product_name}</span>,
            <span key="quantity" className="tabular whitespace-nowrap">{quantity(line)}</span>,
            <span key="price" className="tabular whitespace-nowrap">{money(line.unit_price, version.currency)}</span>,
            <span key="total" className="tabular whitespace-nowrap">{money(line.total, version.currency)}</span>,
          ],
        }))}
      />
      <p className="mt-3 flex items-baseline justify-end gap-3 border-t border-border pt-3">
        <span className="text-sm text-muted-foreground">{t("proposals.grandTotal")}</span>
        <span className="tabular font-display text-xl font-extrabold">{money(version.total, version.currency)}</span>
      </p>
    </div>
  );
}

/** Conditions publiées d'une version : délai, lieu, validité, conditions, mot d'accompagnement. */
export function ProposalTerms({ version }: { version: ProposalVersion }) {
  const t = useTranslations();
  const day = useDay();
  const facts = [
    [t("offers.leadTime"), t("offers.days", { count: version.lead_time_days })],
    [t("requests.deliveryLocation"), version.delivery_location],
    [t("proposals.validUntil"), day(version.valid_until)],
    [t("offers.conditions"), version.conditions],
    [t("proposals.messageFromUs"), version.message],
  ];
  return (
    <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
      {facts.map(([label, value]) => (
        <div key={label}>
          <dt className="text-sm text-muted-foreground">{label}</dt>
          <dd className="font-medium whitespace-pre-line">{value || t("directory.notProvided")}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ProposalHistory({ events }: { events: (ProposalEvent & { actor_name?: string })[] }) {
  const t = useTranslations();
  const format = useFormatter();
  return (
    <div className="mt-6 border-t border-border pt-5">
      <h3 className="mb-3 font-bold">{t("requests.history")}</h3>
      <ol className="space-y-3">
        {events.map((event, index) => (
          <li key={index} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <ProposalBadge status={event.to_status} />
            <span className="text-sm text-muted-foreground">
              {format.dateTime(new Date(event.created_at), { dateStyle: "medium", timeStyle: "short" })} ·{" "}
              {t("offers.version", { version: event.version })}
              {event.actor_name && ` · ${event.actor_name}`}
            </span>
            {event.message && <p className="basis-full whitespace-pre-line">{event.message}</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}
