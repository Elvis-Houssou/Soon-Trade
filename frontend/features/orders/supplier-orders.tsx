"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { DetailReveal } from "@/components/motion/motion";
import { Button, ButtonLink } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage } from "@/components/ui/field";
import { useDay, useMoney } from "@/features/solicitations/shared";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";
import { type Delivery, DeliveryBadge, DeliveryCard, Facts, OrderBadge, OrderLines, ProofUpload, type SupplierOrder } from "./shared";

const REFRESH = [["supplier-orders"]];
// Ce que le fournisseur fait lui-même sur sa livraison ; le reste revient à SOON TRADE.
const MOVES: Record<string, string[]> = {
  planned: ["prepare", "ship"],
  in_preparation: ["ship"],
  in_transit: ["deliver"],
};

function MyDelivery({ delivery }: { delivery: Delivery }) {
  const t = useTranslations();
  const move = useAction((action: string) => api(`/supplier-deliveries/${delivery.id}/${action}`, {}), REFRESH);
  const track = useAction((body: Record<string, string | null>) => api(`/supplier-deliveries/${delivery.id}`, body, "PATCH"), REFRESH);
  const active = !["delivered", "confirmed"].includes(delivery.status);

  return (
    <DeliveryCard
      delivery={delivery}
      actions={
        active ? (
          <div className="w-full space-y-3">
            <div className="flex flex-wrap gap-2">
              {(MOVES[delivery.status] ?? []).map((action) => (
                <Button key={action} size="sm" variant={action === "prepare" ? "outline" : "primary"} disabled={move.pending} onClick={() => move.run(action)}>
                  {t(`orders.deliveryActions.${action}`)}
                </Button>
              ))}
            </div>
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                const values = Object.entries(formValues(event.currentTarget)).map(([key, value]) => [key, value || null]);
                track.run(Object.fromEntries(values));
              }}
            >
              <Field name="carrier" label={t("orders.carrier")} defaultValue={delivery.carrier ?? ""} maxLength={120} />
              <Field name="tracking_number" label={t("orders.tracking")} defaultValue={delivery.tracking_number ?? ""} maxLength={120} />
              <Button type="submit" variant="outline" className="h-11" disabled={track.pending}>
                {t("common.save")}
              </Button>
            </form>
            {(move.errorStatus ?? track.errorStatus) !== undefined && <FormMessage tone="error">{t("orders.conflict")}</FormMessage>}
            <ProofUpload path={`/supplier-deliveries/${delivery.id}/proofs`} refresh={REFRESH} />
            <p className="text-sm text-muted-foreground">{t("orders.supplierProofHint")}</p>
          </div>
        ) : undefined
      }
    />
  );
}

function Details({ part }: { part: SupplierOrder }) {
  const t = useTranslations();
  return (
    <SectionCard title={part.reference} action={<OrderBadge status={part.status} />}>
      <p className="mb-4 text-sm text-muted-foreground">{t("orders.supplierOrderHint")}</p>
      <OrderLines lines={part.terms.lines} currency={part.currency} total={part.total} />
      <div className="mt-4">
        <Facts
          items={[
            [t("offers.leadTime"), t("offers.days", { count: part.terms.lead_time_days })],
            [t("requests.deliveryLocation"), part.terms.delivery_location],
          ]}
        />
      </div>
      <div className="mt-6 border-t border-border pt-5">
        <h3 className="mb-3 font-bold">{t("nav.deliveries")}</h3>
        {part.deliveries.length === 0 ? (
          <p className="text-muted-foreground">{t("orders.noDeliveriesSupplier")}</p>
        ) : (
          <ul className="space-y-3">
            {part.deliveries.map((delivery) => (
              <MyDelivery key={delivery.id} delivery={delivery} />
            ))}
          </ul>
        )}
      </div>
    </SectionCard>
  );
}

/** Page fournisseur « Commandes » : ses bons de commande, à son prix. */
export function SupplierOrdersScreen() {
  const t = useTranslations();
  const money = useMoney();
  const day = useDay();
  const [selectedId, setSelectedId] = useState<string | undefined>(useSearchParams().get("id") ?? undefined);
  const parts = useQuery({ queryKey: ["supplier-orders"], queryFn: () => api<SupplierOrder[]>("/supplier-orders") });
  const selected = parts.data?.find((part) => part.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.orders")} description={t("orders.supplierIntro")} />
      {parts.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {parts.data && (
        <SectionCard title={t("nav.orders")}>
          {parts.data.length === 0 ? (
            <p className="text-muted-foreground">{t("orders.emptySupplier")}</p>
          ) : (
            <DataTable
              columns={[t("columns.reference"), t("columns.product"), t("proposals.grandTotal"), t("orders.receivedOn"), t("columns.status"), ""]}
              rows={parts.data.map((part) => ({
                key: part.id,
                cells: [
                  <span key="reference" className="font-semibold whitespace-nowrap">{part.reference}</span>,
                  part.terms.lines.map((line) => line.product_name).join(", "),
                  <span key="total" className="tabular whitespace-nowrap">{money(part.total, part.currency)}</span>,
                  part.released_at ? day(part.released_at) : "—",
                  <OrderBadge key="status" status={part.status} />,
                  <Button key="open" variant="ghost" size="sm" aria-expanded={part.id === selectedId} onClick={() => setSelectedId(part.id === selectedId ? undefined : part.id)}>
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
          <Details part={selected} />
        </DetailReveal>
      )}
    </div>
  );
}

/** Page fournisseur « Livraisons ». */
export function SupplierDeliveriesScreen() {
  const t = useTranslations();
  const day = useDay();
  const parts = useQuery({ queryKey: ["supplier-orders"], queryFn: () => api<SupplierOrder[]>("/supplier-orders") });
  const deliveries = parts.data?.flatMap((part) => part.deliveries.map((delivery) => ({ part, delivery })));

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.deliveries")} description={t("orders.supplierDeliveriesIntro")} />
      {parts.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {deliveries && (
        <SectionCard title={t("nav.deliveries")}>
          {deliveries.length === 0 ? (
            <p className="text-muted-foreground">{t("orders.noDeliveriesSupplier")}</p>
          ) : (
            <DataTable
              columns={[t("columns.reference"), t("orders.supplierOrder"), t("orders.plannedDate"), t("columns.status"), ""]}
              rows={deliveries.map(({ part, delivery }) => ({
                key: delivery.id,
                cells: [
                  <span key="reference" className="font-semibold whitespace-nowrap">{delivery.reference}</span>,
                  <span key="part" className="whitespace-nowrap">{part.reference}</span>,
                  day(delivery.planned_date),
                  <DeliveryBadge key="status" status={delivery.status} />,
                  <ButtonLink key="open" href={`/supplier/commandes?id=${part.id}`} variant="ghost" size="sm">
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
