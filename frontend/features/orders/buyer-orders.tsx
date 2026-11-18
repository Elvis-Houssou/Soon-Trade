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
import { type BuyerOrder, DeliveryBadge, DeliveryCard, Facts, History, OrderBadge, type OrderStatus, OrderLines } from "./shared";

const REFRESH = [["buyer-orders"], ["buyer-claims"]];
const CATEGORIES = ["quantity", "quality", "delay", "damage", "other"];
const CLAIMABLE = ["confirmed", "in_preparation", "shipped", "delivered", "in_dispute"];

function ClaimForm({ order, onDone }: { order: BuyerOrder; onDone: () => void }) {
  const t = useTranslations();
  const open = useAction((body: Record<string, string | null>) => api("/claims", body), REFRESH);
  return (
    <form
      className="mt-4 space-y-4 rounded-control border border-border p-4"
      onSubmit={(event) => {
        event.preventDefault();
        const values = formValues(event.currentTarget);
        open.run({ ...values, order_id: order.id, delivery_id: values.delivery_id || null }, { onSuccess: onDone });
      }}
    >
      <p className="text-sm text-muted-foreground">{t("claims.formHint")}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField name="category" label={t("claims.category")}>
          {CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {t(`claims.categories.${category}`)}
            </option>
          ))}
        </SelectField>
        {order.deliveries.length > 0 && (
          <SelectField name="delivery_id" label={t("claims.delivery")} defaultValue="">
            <option value="">{t("claims.wholeOrder")}</option>
            {order.deliveries.map((delivery) => (
              <option key={delivery.id} value={delivery.id}>
                {delivery.reference}
              </option>
            ))}
          </SelectField>
        )}
      </div>
      <Field name="subject" label={t("claims.subject")} minLength={3} maxLength={200} required />
      <TextareaField name="description" label={t("claims.description")} minLength={3} maxLength={4000} required />
      {open.errorStatus !== undefined && <FormMessage tone="error">{t(open.errorStatus === 409 ? "claims.notAllowed" : "common.error")}</FormMessage>}
      <Button type="submit" disabled={open.pending}>
        {t("claims.send")}
      </Button>
    </form>
  );
}

function Details({ order }: { order: BuyerOrder }) {
  const t = useTranslations();
  const day = useDay();
  const me = useMe().data;
  const [claiming, setClaiming] = useState(false);
  const confirm = useAction((id: string) => api(`/deliveries/${id}/confirm`, {}), REFRESH);
  const canConfirm = Boolean(me?.permissions.includes("delivery:confirm"));
  const canClaim = Boolean(me?.permissions.includes("claim:create")) && CLAIMABLE.includes(order.status);

  return (
    <SectionCard title={order.reference} action={<OrderBadge status={order.status} />}>
      <p className="mb-4 text-sm text-muted-foreground">
        {t("orders.forRequest", { request: order.request_reference, proposal: order.terms.proposal_reference, version: order.terms.version })}
      </p>
      {order.status === "created" && (
        <div className="mb-4 rounded-control bg-primary-soft px-3 py-2 text-primary-soft-foreground">
          <p className="text-sm">{t("orders.awaitingConfirmation")}</p>
        </div>
      )}
      {order.status === "cancelled" && order.history.at(-1)?.message && (
        <div className="mb-4 rounded-control bg-danger-soft px-3 py-2 text-danger-foreground">
          <p className="text-sm font-semibold">{t("orders.cancelledBecause")}</p>
          <p className="whitespace-pre-line">{order.history.at(-1)?.message}</p>
        </div>
      )}

      <h3 className="mb-2 font-bold">{t("orders.acceptedTerms")}</h3>
      <OrderLines lines={order.terms.lines} currency={order.currency} total={order.total} />
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

      <div className="mt-6 border-t border-border pt-5">
        <h3 className="mb-3 font-bold">{t("nav.deliveries")}</h3>
        {order.deliveries.length === 0 ? (
          <p className="text-muted-foreground">{t("orders.noDeliveriesBuyer")}</p>
        ) : (
          <ul className="space-y-3">
            {order.deliveries.map((delivery) => (
              <DeliveryCard
                key={delivery.id}
                delivery={delivery}
                actions={
                  delivery.status === "delivered" && canConfirm ? (
                    <>
                      <Button size="sm" disabled={confirm.pending} onClick={() => confirm.run(delivery.id)}>
                        {t("orders.confirmReception")}
                      </Button>
                      <span className="text-sm text-muted-foreground">{t("orders.problemHint")}</span>
                    </>
                  ) : undefined
                }
              />
            ))}
          </ul>
        )}
        {confirm.errorStatus !== undefined && <FormMessage tone="error">{t("orders.conflict")}</FormMessage>}
      </div>

      {canClaim && (
        <div className="mt-6 border-t border-border pt-5">
          <Button variant="outline" aria-expanded={claiming} onClick={() => setClaiming((open) => !open)}>
            {t("claims.open")}
          </Button>
          {claiming && <ClaimForm order={order} onDone={() => setClaiming(false)} />}
          <ButtonLink href="/buyer/reclamations" variant="ghost" size="sm" className="ml-2">
            {t("nav.claims")}
          </ButtonLink>
        </div>
      )}

      <History events={order.history} badge={(value) => <OrderBadge status={value as OrderStatus} />} />
    </SectionCard>
  );
}

/** Page acheteur « Commandes ». */
export function BuyerOrdersScreen() {
  const t = useTranslations();
  const money = useMoney();
  const day = useDay();
  const [selectedId, setSelectedId] = useState<string | undefined>(useSearchParams().get("id") ?? undefined);
  const orders = useQuery({ queryKey: ["buyer-orders"], queryFn: () => api<BuyerOrder[]>("/orders") });
  const selected = orders.data?.find((order) => order.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.orders")} description={t("orders.buyerIntro")} />
      {orders.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {orders.data && (
        <SectionCard title={t("nav.orders")}>
          {orders.data.length === 0 ? (
            <p className="text-muted-foreground">{t("orders.emptyBuyer")}</p>
          ) : (
            <DataTable
              columns={[t("columns.reference"), t("proposals.request"), t("proposals.grandTotal"), t("columns.date"), t("columns.status"), ""]}
              rows={orders.data.map((order) => ({
                key: order.id,
                cells: [
                  <span key="reference" className="font-semibold whitespace-nowrap">{order.reference}</span>,
                  <span key="request" className="whitespace-nowrap">{order.request_reference}</span>,
                  <span key="total" className="tabular whitespace-nowrap">{money(order.total, order.currency)}</span>,
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

/** Page acheteur « Livraisons » : toutes les livraisons de ses commandes. */
export function BuyerDeliveriesScreen() {
  const t = useTranslations();
  const day = useDay();
  const orders = useQuery({ queryKey: ["buyer-orders"], queryFn: () => api<BuyerOrder[]>("/orders") });
  const deliveries = orders.data?.flatMap((order) => order.deliveries.map((delivery) => ({ order, delivery })));

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.deliveries")} description={t("orders.deliveriesIntro")} />
      {orders.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {deliveries && (
        <SectionCard title={t("nav.deliveries")}>
          {deliveries.length === 0 ? (
            <p className="text-muted-foreground">{t("orders.noDeliveriesBuyer")}</p>
          ) : (
            <DataTable
              columns={[t("columns.reference"), t("orders.order"), t("orders.plannedDate"), t("orders.carrier"), t("columns.status"), ""]}
              rows={deliveries.map(({ order, delivery }) => ({
                key: delivery.id,
                cells: [
                  <span key="reference" className="font-semibold whitespace-nowrap">{delivery.reference}</span>,
                  <span key="order" className="whitespace-nowrap">{order.reference}</span>,
                  day(delivery.planned_date),
                  delivery.carrier ?? "—",
                  <DeliveryBadge key="status" status={delivery.status} />,
                  <ButtonLink key="open" href={`/buyer/commandes?id=${order.id}`} variant="ghost" size="sm">
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
