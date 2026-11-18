"use client";

import { useFormatter, useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { DataTable } from "@/components/dashboard/widgets";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FormMessage } from "@/components/ui/field";
import { useQuantity } from "@/features/requests/shared";
import { useDay, useMoney } from "@/features/solicitations/shared";
import { api } from "@/lib/api";
import { useAction } from "@/lib/use-action";

export type OrderStatus = "created" | "confirmed" | "in_preparation" | "shipped" | "delivered" | "closed" | "cancelled" | "in_dispute";
export type DeliveryStatus = "planned" | "in_preparation" | "in_transit" | "delivered" | "confirmed" | "incident";
export type ClaimStatus = "open" | "under_review" | "resolved" | "rejected" | "closed";

export type Line = { product_name: string; quantity: string; unit: string; unit_price: string; total: string };

export type Terms = {
  proposal_reference: string;
  version: number;
  currency: string;
  lead_time_days: number;
  valid_until: string;
  delivery_location: string;
  conditions: string | null;
  message: string | null;
  lines: Line[];
};

export type SupplierTerms = { currency: string; lead_time_days: number; delivery_location: string; lines: Line[] };

export type Proof = { id: string; filename: string; buyer_visible?: boolean };

export type StatusEvent = {
  created_at: string;
  to_status: string;
  /** Présents uniquement dans les réponses internes. */
  from_status?: string | null;
  actor_name?: string | null;
  message?: string | null;
};

export type Delivery = {
  id: string;
  reference: string;
  status: DeliveryStatus;
  description: string;
  planned_date: string;
  carrier: string | null;
  tracking_number: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  confirmed_at: string | null;
  proofs: Proof[];
  history: StatusEvent[];
};

export type InternalDelivery = Delivery & {
  order_id: string;
  order_reference: string;
  supplier_order_id: string | null;
  supplier_order_reference: string | null;
  supplier_name: string | null;
};

export type BuyerOrder = {
  id: string;
  reference: string;
  status: OrderStatus;
  created_at: string;
  confirmed_at: string | null;
  request_reference: string;
  currency: string;
  total: string;
  terms: Terms;
  deliveries: Delivery[];
  history: StatusEvent[];
};

export type SupplierOrder = {
  id: string;
  reference: string;
  status: OrderStatus;
  released_at: string | null;
  currency: string;
  total: string;
  terms: SupplierTerms;
  deliveries: Delivery[];
};

export type InternalOrder = {
  id: string;
  reference: string;
  status: OrderStatus;
  status_before_dispute: OrderStatus | null;
  created_at: string;
  confirmed_at: string | null;
  buyer_name: string;
  proposal_reference: string;
  request_reference: string;
  currency: string;
  buyer_total: string;
  cost_total: string;
  margin: string;
  terms: Terms;
  supplier_orders: { id: string; reference: string; supplier_name: string; released_at: string | null; supplier_total: string; terms: SupplierTerms }[];
  deliveries: InternalDelivery[];
  events: StatusEvent[];
};

const ORDER_TONE: Record<OrderStatus, Tone> = {
  created: "neutral",
  confirmed: "primary",
  in_preparation: "primary",
  shipped: "warning",
  delivered: "success",
  closed: "neutral",
  cancelled: "danger",
  in_dispute: "danger",
};
const DELIVERY_TONE: Record<DeliveryStatus, Tone> = {
  planned: "neutral",
  in_preparation: "primary",
  in_transit: "warning",
  delivered: "success",
  confirmed: "success",
  incident: "danger",
};
const CLAIM_TONE: Record<ClaimStatus, Tone> = {
  open: "warning",
  under_review: "primary",
  resolved: "success",
  rejected: "danger",
  closed: "neutral",
};

export function OrderBadge({ status }: { status: OrderStatus }) {
  const t = useTranslations("orderStatus");
  return <Badge tone={ORDER_TONE[status]}>{t(status)}</Badge>;
}

export function DeliveryBadge({ status }: { status: DeliveryStatus }) {
  const t = useTranslations("deliveryStatus");
  return <Badge tone={DELIVERY_TONE[status]}>{t(status)}</Badge>;
}

export function ClaimBadge({ status }: { status: ClaimStatus }) {
  const t = useTranslations("claimStatus");
  return <Badge tone={CLAIM_TONE[status]}>{t(status)}</Badge>;
}

/** Lignes figées d'une commande ou d'un bon, et leur total. */
export function OrderLines({ lines, currency, total }: { lines: Line[]; currency: string; total: string }) {
  const t = useTranslations();
  const money = useMoney();
  const quantity = useQuantity();
  return (
    <div>
      <DataTable
        columns={[t("columns.product"), t("columns.quantity"), t("offers.unitPrice"), t("offers.total")]}
        rows={lines.map((line, index) => ({
          key: String(index),
          cells: [
            <span key="product" className="font-medium">{line.product_name}</span>,
            <span key="quantity" className="tabular whitespace-nowrap">{quantity(line)}</span>,
            <span key="price" className="tabular whitespace-nowrap">{money(line.unit_price, currency)}</span>,
            <span key="total" className="tabular whitespace-nowrap">{money(line.total, currency)}</span>,
          ],
        }))}
      />
      <p className="mt-3 flex items-baseline justify-end gap-3 border-t border-border pt-3">
        <span className="text-sm text-muted-foreground">{t("proposals.grandTotal")}</span>
        <span className="tabular font-display text-xl font-extrabold">{money(total, currency)}</span>
      </p>
    </div>
  );
}

export function Facts({ items }: { items: [string, ReactNode][] }) {
  const t = useTranslations();
  return (
    <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className="text-sm text-muted-foreground">{label}</dt>
          <dd className="font-medium whitespace-pre-line">{value || t("directory.notProvided")}</dd>
        </div>
      ))}
    </dl>
  );
}

export function History({ events, badge }: { events: StatusEvent[]; badge: (status: string) => ReactNode }) {
  const t = useTranslations();
  const format = useFormatter();
  return (
    <div className="mt-6 border-t border-border pt-5">
      <h3 className="mb-3 font-bold">{t("requests.history")}</h3>
      <ol className="space-y-3">
        {events.map((event, index) => (
          <li key={index} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            {badge(event.to_status)}
            <span className="text-sm text-muted-foreground">
              {format.dateTime(new Date(event.created_at), { dateStyle: "medium", timeStyle: "short" })}
              {event.actor_name && ` · ${event.actor_name}`}
            </span>
            {event.message && <p className="basis-full whitespace-pre-line">{event.message}</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Une livraison : ce qui part, quand, avec qui, ses preuves ; `actions` selon l'espace. */
export function DeliveryCard({ delivery, extra, actions }: { delivery: Delivery; extra?: ReactNode; actions?: ReactNode }) {
  const t = useTranslations();
  const day = useDay();
  return (
    <li className="rounded-control border border-border p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold">
          {delivery.reference}
          {extra && <span className="block text-sm font-normal text-muted-foreground">{extra}</span>}
        </p>
        <DeliveryBadge status={delivery.status} />
      </div>
      <Facts
        items={[
          [t("orders.deliveryContent"), delivery.description],
          [t("orders.plannedDate"), day(delivery.planned_date)],
          [t("orders.carrier"), delivery.carrier],
          [t("orders.tracking"), delivery.tracking_number],
          [t("orders.shippedAt"), delivery.shipped_at && day(delivery.shipped_at)],
          [t("orders.deliveredAt"), delivery.delivered_at && day(delivery.delivered_at)],
        ]}
      />
      {delivery.proofs.length > 0 && (
        <div className="mt-3">
          <p className="text-sm text-muted-foreground">{t("orders.proofs")}</p>
          <ProofLinks delivery={delivery} />
        </div>
      )}
      {actions && <div className="mt-4 flex flex-wrap items-start gap-3 border-t border-border pt-3">{actions}</div>}
    </li>
  );
}

function ProofLinks({ delivery }: { delivery: Delivery }) {
  const t = useTranslations();
  return (
    <span className="flex flex-wrap gap-1">
      {delivery.proofs.map((proof) => (
        <Button
          key={proof.id}
          variant="ghost"
          size="sm"
          className="max-w-64 truncate"
          onClick={async () => {
            const { url } = await api<{ url: string }>(`/deliveries/${delivery.id}/proofs/${proof.id}/url`);
            window.open(url, "_blank", "noopener");
          }}
        >
          {proof.filename}
          {proof.buyer_visible !== undefined && ` · ${t(proof.buyer_visible ? "orders.visibleToBuyer" : "orders.internalOnly")}`}
        </Button>
      ))}
    </span>
  );
}

/** Dépôt d'une preuve (PDF, JPEG, PNG) sur une livraison. */
export function ProofUpload({ path, refresh, withVisibility = false }: { path: string; refresh: string[][]; withVisibility?: boolean }) {
  const t = useTranslations();
  const upload = useAction((data: FormData) => api(path, data), refresh);
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        upload.run(new FormData(form), { onSuccess: () => form.reset() });
      }}
    >
      <Field name="file" type="file" label={t("orders.addProof")} accept="application/pdf,image/jpeg,image/png" className="py-2" required />
      {withVisibility && (
        <label className="flex h-11 items-center gap-2 text-sm">
          <input type="checkbox" name="buyer_visible" value="true" className="size-4 accent-primary" />
          {t("orders.showToBuyer")}
        </label>
      )}
      <Button type="submit" variant="outline" className="h-11" disabled={upload.pending}>
        {t("documents.upload")}
      </Button>
      {upload.errorStatus !== undefined && <FormMessage tone="error">{t("documents.invalid")}</FormMessage>}
    </form>
  );
}
