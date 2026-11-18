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
import { Field, FormMessage, SelectField, TextareaField } from "@/components/ui/field";
import { useDay, useMoney } from "@/features/solicitations/shared";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";
import { cn } from "@/lib/utils";
import {
  DeliveryBadge,
  DeliveryCard,
  Facts,
  History,
  type InternalDelivery,
  type InternalOrder,
  OrderBadge,
  type OrderStatus,
  OrderLines,
  ProofUpload,
} from "./shared";

const REFRESH = [["internal-orders"], ["internal-deliveries"]];
// Actions logistiques possibles selon l'état d'une livraison.
const DELIVERY_MOVES: Record<string, string[]> = {
  planned: ["prepare", "ship"],
  in_preparation: ["ship"],
  in_transit: ["deliver", "incident"],
  delivered: ["incident"],
  incident: ["resume"],
};

function useRefusal() {
  const t = useTranslations();
  return (status: number) => t(status === 400 ? "orders.refused400" : status === 409 ? "orders.conflict" : "common.error");
}

/** Planification d'une livraison : la commande entière ou la part d'un fournisseur. */
function PlanDelivery({ order }: { order: InternalOrder }) {
  const t = useTranslations();
  const refusal = useRefusal();
  const plan = useAction((body: Record<string, string | null>) => api(`/internal/orders/${order.id}/deliveries`, body), REFRESH);
  return (
    <form
      className="space-y-4 rounded-control border border-border p-4"
      onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const values = Object.entries(formValues(form)).map(([key, value]) => [key, value || null]);
        plan.run(Object.fromEntries(values), { onSuccess: () => form.reset() });
      }}
    >
      <h4 className="font-semibold">{t("orders.planDelivery")}</h4>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field name="description" label={t("orders.deliveryContent")} hint={t("orders.contentHint")} minLength={2} maxLength={500} required />
        <Field name="planned_date" label={t("orders.plannedDate")} type="date" required />
        <Field name="carrier" label={t("orders.carrier")} maxLength={120} />
        <Field name="tracking_number" label={t("orders.tracking")} maxLength={120} />
        {order.supplier_orders.length > 0 && (
          <SelectField name="supplier_order_id" label={t("orders.forPart")} defaultValue={order.supplier_orders[0].id}>
            {order.supplier_orders.map((part) => (
              <option key={part.id} value={part.id}>
                {part.reference} · {part.supplier_name}
              </option>
            ))}
            <option value="">{t("orders.wholeOrder")}</option>
          </SelectField>
        )}
      </div>
      {plan.errorStatus !== undefined && <FormMessage tone="error">{refusal(plan.errorStatus)}</FormMessage>}
      <Button type="submit" disabled={plan.pending}>
        {t("orders.plan")}
      </Button>
    </form>
  );
}

function DeliveryActions({ delivery }: { delivery: InternalDelivery }) {
  const t = useTranslations();
  const refusal = useRefusal();
  const [incident, setIncident] = useState(false);
  const move = useAction(({ action, message }: { action: string; message?: string }) => api(`/internal/deliveries/${delivery.id}/${action}`, { message }), REFRESH);
  const moves = DELIVERY_MOVES[delivery.status] ?? [];
  return (
    <div className="w-full space-y-3">
      <div className="flex flex-wrap gap-2">
        {moves.map((action) =>
          action === "incident" ? (
            <Button key={action} variant="ghost" size="sm" aria-expanded={incident} onClick={() => setIncident((open) => !open)}>
              {t("orders.deliveryActions.incident")}
            </Button>
          ) : (
            <Button key={action} variant={action === "deliver" || action === "ship" ? "primary" : "outline"} size="sm" disabled={move.pending} onClick={() => move.run({ action })}>
              {t(`orders.deliveryActions.${action}`)}
            </Button>
          ),
        )}
      </div>
      {incident && (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            const message = String(new FormData(event.currentTarget).get("message") ?? "").trim();
            move.run({ action: "incident", message }, { onSuccess: () => setIncident(false) });
          }}
        >
          <TextareaField name="message" label={t("orders.incidentNote")} hint={t("orders.incidentHint")} maxLength={2000} required />
          <Button type="submit" size="sm" disabled={move.pending}>
            {t("orders.deliveryActions.incident")}
          </Button>
        </form>
      )}
      {move.errorStatus !== undefined && <FormMessage tone="error">{refusal(move.errorStatus)}</FormMessage>}
      {delivery.status !== "confirmed" && <ProofUpload path={`/internal/deliveries/${delivery.id}/proofs`} refresh={REFRESH} withVisibility />}
    </div>
  );
}

function Details({ order }: { order: InternalOrder }) {
  const t = useTranslations();
  const money = useMoney();
  const day = useDay();
  const me = useMe().data;
  const refusal = useRefusal();
  const [cancelling, setCancelling] = useState(false);
  const can = (permission: string) => Boolean(me?.permissions.includes(permission));
  const act = useAction(({ path, message }: { path: string; message?: string }) => api(`/internal/orders/${order.id}/${path}`, { message }), REFRESH);
  const status = order.status;
  const plannable = ["confirmed", "in_preparation", "shipped"].includes(status);

  return (
    <SectionCard title={`${order.reference} · ${order.buyer_name}`} action={<OrderBadge status={status} />}>
      <p className="mb-4 text-sm text-muted-foreground">
        {t("orders.basedOn", { proposal: order.proposal_reference, version: order.terms.version, request: order.request_reference })}
      </p>
      {status === "in_dispute" && order.status_before_dispute && (
        <div className="mb-4 rounded-control bg-danger-soft px-3 py-2 text-danger-foreground">
          <p className="text-sm">{t("orders.disputeHint", { status: t(`orderStatus.${order.status_before_dispute}`) })}</p>
        </div>
      )}

      <div className="mb-5 grid gap-3 rounded-control bg-surface-muted p-4 sm:grid-cols-3">
        <p>
          <span className="block text-sm text-muted-foreground">{t("orders.buyerTotal")}</span>
          <span className="tabular font-display text-lg font-extrabold">{money(order.buyer_total, order.currency)}</span>
        </p>
        <p>
          <span className="block text-sm text-muted-foreground">{t("proposals.costTotal")}</span>
          <span className="tabular font-semibold">{money(order.cost_total, order.currency)}</span>
        </p>
        <p className={cn(Number(order.margin) < 0 && "text-danger-foreground")}>
          <span className="block text-sm text-muted-foreground">{t("proposals.margin")}</span>
          <span className="tabular font-semibold">{money(order.margin, order.currency)}</span>
        </p>
      </div>

      <h3 className="mb-2 font-bold">{t("orders.acceptedTerms")}</h3>
      <OrderLines lines={order.terms.lines} currency={order.currency} total={order.buyer_total} />
      <div className="mt-4">
        <Facts
          items={[
            [t("offers.leadTime"), t("offers.days", { count: order.terms.lead_time_days })],
            [t("requests.deliveryLocation"), order.terms.delivery_location],
            [t("offers.conditions"), order.terms.conditions],
            [t("orders.confirmedAt"), order.confirmed_at && day(order.confirmed_at)],
          ]}
        />
      </div>

      {order.supplier_orders.length > 0 && (
        <div className="mt-6 border-t border-border pt-5">
          <h3 className="font-bold">{t("orders.supplierOrders")}</h3>
          <p className="mb-3 text-sm text-muted-foreground">{t("orders.supplierOrdersHint")}</p>
          <DataTable
            columns={[t("columns.reference"), t("sourcing.supplier"), t("proposals.costTotal"), t("orders.released")]}
            rows={order.supplier_orders.map((part) => ({
              key: part.id,
              cells: [
                <span key="reference" className="font-semibold whitespace-nowrap">{part.reference}</span>,
                part.supplier_name,
                <span key="total" className="tabular whitespace-nowrap">{money(part.supplier_total, order.currency)}</span>,
                part.released_at ? day(part.released_at) : t("orders.notReleased"),
              ],
            }))}
          />
        </div>
      )}

      {act.errorStatus !== undefined && (
        <div className="mt-4">
          <FormMessage tone="error">{refusal(act.errorStatus)}</FormMessage>
        </div>
      )}
      <div className="mt-5 flex flex-wrap gap-3">
        {status === "created" && can("order:manage") && (
          <Button disabled={act.pending} onClick={() => act.run({ path: "confirm" })}>
            {t("orders.actions.confirm")}
          </Button>
        )}
        {status === "confirmed" && can("logistics:manage") && (
          <Button disabled={act.pending} onClick={() => act.run({ path: "prepare" })}>
            {t("orders.actions.prepare")}
          </Button>
        )}
        {status === "delivered" && can("order:manage") && (
          <Button disabled={act.pending} onClick={() => act.run({ path: "close" })}>
            {t("orders.actions.close")}
          </Button>
        )}
        {["created", "confirmed", "in_preparation"].includes(status) && can("order:manage") && (
          <Button variant="ghost" disabled={act.pending} aria-expanded={cancelling} onClick={() => setCancelling((open) => !open)}>
            {t("orders.actions.cancel")}
          </Button>
        )}
      </div>
      {cancelling && (
        <form
          className="mt-4 space-y-3 rounded-control border border-border p-4"
          onSubmit={(event) => {
            event.preventDefault();
            const message = String(new FormData(event.currentTarget).get("message") ?? "").trim();
            act.run({ path: "cancel", message }, { onSuccess: () => setCancelling(false) });
          }}
        >
          <TextareaField name="message" label={t("orders.cancelReason")} hint={t("orders.cancelHint")} maxLength={2000} required />
          <Button type="submit" disabled={act.pending}>
            {t("orders.actions.cancel")}
          </Button>
        </form>
      )}

      <div className="mt-6 border-t border-border pt-5">
        <h3 className="mb-3 font-bold">{t("nav.deliveries")}</h3>
        {order.deliveries.length === 0 ? (
          <p className="mb-3 text-muted-foreground">{t("orders.noDeliveries")}</p>
        ) : (
          <ul className="mb-4 space-y-3">
            {order.deliveries.map((delivery) => (
              <DeliveryCard
                key={delivery.id}
                delivery={delivery}
                extra={delivery.supplier_name ? `${delivery.supplier_order_reference} · ${delivery.supplier_name}` : t("orders.wholeOrder")}
                actions={can("logistics:manage") && !["cancelled", "closed"].includes(status) ? <DeliveryActions delivery={delivery} /> : undefined}
              />
            ))}
          </ul>
        )}
        {plannable && can("logistics:manage") && <PlanDelivery order={order} />}
      </div>

      <History events={order.events} badge={(value) => <OrderBadge status={value as OrderStatus} />} />
    </SectionCard>
  );
}

/** Page interne « Commandes ». */
export function InternalOrdersScreen() {
  const t = useTranslations();
  const money = useMoney();
  const day = useDay();
  const [selectedId, setSelectedId] = useState<string | undefined>(useSearchParams().get("id") ?? undefined);
  const orders = useQuery({ queryKey: ["internal-orders"], queryFn: () => api<InternalOrder[]>("/internal/orders") });
  const selected = orders.data?.find((order) => order.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.orders")} description={t("orders.internalIntro")} />
      {orders.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {orders.data && (
        <SectionCard title={t("nav.orders")}>
          {orders.data.length === 0 ? (
            <p className="text-muted-foreground">{t("orders.emptyInternal")}</p>
          ) : (
            <DataTable
              columns={[t("columns.reference"), t("proposals.buyer"), t("orders.buyerTotal"), t("columns.date"), t("columns.status"), ""]}
              rows={orders.data.map((order) => ({
                key: order.id,
                cells: [
                  <span key="reference" className="font-semibold whitespace-nowrap">{order.reference}</span>,
                  order.buyer_name,
                  <span key="total" className="tabular whitespace-nowrap">{money(order.buyer_total, order.currency)}</span>,
                  day(order.created_at),
                  <OrderBadge key="status" status={order.status} />,
                  <Button key="open" variant="ghost" size="sm" aria-expanded={order.id === selectedId} onClick={() => setSelectedId(order.id === selectedId ? undefined : order.id)}>
                    {t("requests.open")}
                  </Button>,
                ],
              }))}
            />
          )}
        </SectionCard>
      )}
      {selected && (
        <DetailReveal key={selected.id}>
          <Details key={`${selected.id}-${selected.status}`} order={selected} />
        </DetailReveal>
      )}
    </div>
  );
}

/** Page interne « Logistique » : toutes les livraisons ; on agit depuis la commande. */
export function LogisticsScreen() {
  const t = useTranslations();
  const day = useDay();
  const deliveries = useQuery({ queryKey: ["internal-deliveries"], queryFn: () => api<InternalDelivery[]>("/internal/deliveries") });

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.logistics")} description={t("orders.logisticsIntro")} />
      {deliveries.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {deliveries.data && (
        <SectionCard title={t("nav.deliveries")}>
          {deliveries.data.length === 0 ? (
            <p className="text-muted-foreground">{t("orders.noDeliveries")}</p>
          ) : (
            <DataTable
              columns={[t("columns.reference"), t("orders.order"), t("sourcing.supplier"), t("orders.plannedDate"), t("columns.status"), ""]}
              rows={deliveries.data.map((delivery) => ({
                key: delivery.id,
                cells: [
                  <span key="reference" className="font-semibold whitespace-nowrap">{delivery.reference}</span>,
                  <span key="order" className="whitespace-nowrap">{delivery.order_reference}</span>,
                  delivery.supplier_name ?? t("orders.wholeOrder"),
                  day(delivery.planned_date),
                  <DeliveryBadge key="status" status={delivery.status} />,
                  <ButtonLink key="open" href={`/internal/commandes?id=${delivery.order_id}`} variant="ghost" size="sm">
                    {t("orders.openOrder")}
                  </ButtonLink>,
                ],
              }))}
            />
          )}
        </SectionCard>
      )}
    </div>
  );
}
