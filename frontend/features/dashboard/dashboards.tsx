"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  ChevronRight,
  CircleCheck,
  ClipboardCheck,
  FileText,
  Handshake,
  HandCoins,
  Inbox,
  Layers,
  Mail,
  Package,
  Percent,
  Search,
  Send,
  ShieldCheck,
  Tag,
  Truck,
  Wallet,
} from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useMe } from "@/components/auth/session";
import { TrendChart } from "@/components/dashboard/trend-chart";
import { DataTable, HeroBanner, PageHeading, StatCard, StatGrid } from "@/components/dashboard/widgets";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card, SectionCard } from "@/components/ui/card";
import { FormMessage } from "@/components/ui/field";
import { type RequestStatus, StatusBadge, useQuantity } from "@/features/requests/shared";
import { SolicitationBadge, type SolicitationStatus, useDay } from "@/features/solicitations/shared";
import { api } from "@/lib/api";

type Point = { month: string; value: number | string };

type InternalData = {
  counts: Record<"to_qualify" | "in_sourcing" | "proposals_open" | "orders_active" | "deliveries_in_transit" | "open_claims", number>;
  /** Absent pour les rôles qui ne lisent pas les rapports. */
  money?: { currency: string; revenue: string; margin: string };
  workflow: Record<"requests" | "sourcing" | "offers" | "proposals" | "orders" | "deliveries" | "closed", number>;
  trend: Point[];
  in_progress: { id: string; reference: string; buyer: string; product: string; quantity: string; unit: string; status: RequestStatus; assignee: string | null; created_at: string }[];
  recent: { kind: "request" | "order" | "offer"; at: string; reference: string; status: string; party: string }[];
};

type BuyerData = {
  counts: Record<"requests_active" | "proposals_waiting" | "orders_active" | "deliveries_in_transit" | "deliveries_to_confirm" | "open_claims", number>;
  money: { currency: string; spend: string };
  trend: Point[];
  recent_requests: { id: string; reference: string; product: string; quantity: string; unit: string; status: RequestStatus; created_at: string }[];
};

type SupplierData = {
  counts: Record<"solicitations_open" | "offers_pending" | "offers_retained" | "orders_active" | "deliveries_to_ship", number>;
  money: { currency: string; sales: string };
  trend: Point[];
  open_solicitations: { id: string; reference: string; product: string; quantity: string; unit: string; deadline: string; status: SolicitationStatus }[];
};

function useDashboard<T>() {
  return useQuery({ queryKey: ["dashboard"], queryFn: () => api<T>("/dashboard") });
}

function Failed() {
  const t = useTranslations("common");
  return <FormMessage tone="error">{t("unavailable")}</FormMessage>;
}

export function BuyerDashboard() {
  const t = useTranslations();
  const me = useMe().data;
  const quantity = useQuantity();
  const day = useDay();
  const { data, error } = useDashboard<BuyerData>();

  return (
    <>
      <PageHeading title={t("buyer.greeting", { name: me?.organization.name ?? "" })} description={t("buyer.description")} />
      <div className="space-y-5">
        <HeroBanner
          image="port"
          title={t("buyer.heroTitle")}
          points={[
            { icon: Search, label: t("hero.sourcing") },
            { icon: Handshake, label: t("hero.negotiation") },
            { icon: ShieldCheck, label: t("hero.securePurchase") },
            { icon: Truck, label: t("hero.tracking") },
          ]}
          cta={{ href: "/buyer/nouvelle-demande", label: t("buyer.cta") }}
        />
        {error && <Failed />}
        {data && (
          <>
            <StatGrid className="xl:grid-cols-3 2xl:grid-cols-6">
              <StatCard icon={FileText} label={t("dashboard.requestsActive")} value={data.counts.requests_active} />
              <StatCard icon={Tag} label={t("dashboard.proposalsWaiting")} value={data.counts.proposals_waiting} />
              <StatCard icon={Package} label={t("dashboard.ordersActive")} value={data.counts.orders_active} />
              <StatCard
                icon={Truck}
                label={t("dashboard.deliveriesInTransit")}
                value={data.counts.deliveries_in_transit}
                footnote={data.counts.deliveries_to_confirm > 0 ? <Badge tone="warning">{t("dashboard.toConfirm", { count: data.counts.deliveries_to_confirm })}</Badge> : undefined}
              />
              <StatCard icon={AlertCircle} label={t("dashboard.openClaims")} value={data.counts.open_claims} />
              <StatCard icon={Wallet} label={t("dashboard.spend")} value={Number(data.money.spend)} suffix="FCFA" />
            </StatGrid>
            <div className="grid gap-5 xl:grid-cols-[3fr_2fr]">
              <SectionCard title={t("buyer.recentRequests")} href="/buyer/demandes">
                {data.recent_requests.length === 0 ? (
                  <p className="text-muted-foreground">{t("requests.empty")}</p>
                ) : (
                  <DataTable
                    columns={[t("columns.reference"), t("columns.product"), t("columns.quantity"), t("columns.status"), t("columns.date")]}
                    rows={data.recent_requests.map((request) => ({
                      key: request.id,
                      cells: [
                        <span key="ref" className="tabular whitespace-nowrap font-medium">{request.reference}</span>,
                        <span key="product" className="font-semibold">{request.product}</span>,
                        <span key="quantity" className="tabular whitespace-nowrap">{quantity(request)}</span>,
                        <StatusBadge key="status" status={request.status} />,
                        <span key="date" className="text-muted-foreground">{day(request.created_at)}</span>,
                      ],
                    }))}
                  />
                )}
              </SectionCard>
              <SectionCard title={t("dashboard.spendTrend")}>
                <TrendChart points={data.trend} unit="FCFA" />
              </SectionCard>
            </div>
          </>
        )}
      </div>
    </>
  );
}

export function SupplierDashboard() {
  const t = useTranslations();
  const me = useMe().data;
  const quantity = useQuantity();
  const day = useDay();
  const { data, error } = useDashboard<SupplierData>();

  return (
    <>
      <PageHeading title={t("supplier.greeting", { name: me?.organization.name ?? "" })} description={t("supplier.description")} />
      <div className="space-y-5">
        <HeroBanner
          image="marchandises"
          title={t("supplier.heroTitle")}
          points={[
            { icon: Mail, label: t("supplier.pointReceive") },
            { icon: Tag, label: t("supplier.pointOffer") },
            { icon: HandCoins, label: t("supplier.pointPayouts") },
          ]}
          cta={{ href: "/supplier/catalogue", label: t("supplier.cta") }}
        />
        {error && <Failed />}
        {data && (
          <>
            <StatGrid className="xl:grid-cols-3 2xl:grid-cols-6">
              <StatCard icon={Mail} label={t("dashboard.solicitationsOpen")} value={data.counts.solicitations_open} />
              <StatCard icon={Tag} label={t("dashboard.offersPending")} value={data.counts.offers_pending} />
              <StatCard icon={CircleCheck} label={t("dashboard.offersRetained")} value={data.counts.offers_retained} />
              <StatCard icon={Package} label={t("dashboard.ordersActive")} value={data.counts.orders_active} />
              <StatCard icon={Truck} label={t("dashboard.deliveriesToShip")} value={data.counts.deliveries_to_ship} />
              <StatCard icon={Wallet} label={t("dashboard.sales")} value={Number(data.money.sales)} suffix="FCFA" />
            </StatGrid>
            <div className="grid gap-5 xl:grid-cols-[3fr_2fr]">
              <SectionCard title={t("supplier.recentSolicitations")} href="/supplier/sollicitations">
                {data.open_solicitations.length === 0 ? (
                  <p className="text-muted-foreground">{t("solicitations.empty")}</p>
                ) : (
                  <DataTable
                    columns={[t("columns.reference"), t("columns.product"), t("columns.quantity"), t("solicitations.deadline"), t("columns.status"), ""]}
                    rows={data.open_solicitations.map((solicitation) => ({
                      key: solicitation.id,
                      cells: [
                        <span key="ref" className="tabular whitespace-nowrap font-medium">{solicitation.reference}</span>,
                        <span key="product" className="font-semibold">{solicitation.product}</span>,
                        <span key="quantity" className="tabular whitespace-nowrap">{quantity(solicitation)}</span>,
                        day(solicitation.deadline),
                        <SolicitationBadge key="status" status={solicitation.status} />,
                        <ButtonLink key="reply" href={`/supplier/sollicitations?id=${solicitation.id}`} variant="ghost" size="sm">
                          {t("supplier.reply")}
                        </ButtonLink>,
                      ],
                    }))}
                  />
                )}
              </SectionCard>
              <SectionCard title={t("supplier.salesTrend")}>
                <TrendChart points={data.trend} unit="FCFA" />
              </SectionCard>
            </div>
          </>
        )}
      </div>
    </>
  );
}

const WORKFLOW = [
  ["requests", "stepRequests", FileText],
  ["sourcing", "stepSourcing", Search],
  ["offers", "stepOffers", Tag],
  ["proposals", "stepProposals", Send],
  ["orders", "stepOrders", Package],
  ["deliveries", "stepDeliveries", Truck],
  ["closed", "stepClosed", CircleCheck],
] as const;

export function InternalDashboard() {
  const t = useTranslations();
  const format = useFormatter();
  const quantity = useQuantity();
  const day = useDay();
  const { data, error } = useDashboard<InternalData>();

  return (
    <>
      <PageHeading title={t("internal.heading")} description={t("internal.description")} />
      <div className="space-y-5">
        <HeroBanner
          image="port"
          title={t("internal.heroTitle")}
          points={[
            { icon: Search, label: t("hero.sourcing") },
            { icon: Handshake, label: t("hero.negotiation") },
            { icon: ShieldCheck, label: t("hero.transaction") },
            { icon: Truck, label: t("hero.delivery") },
          ]}
          cta={{ href: "/internal/demandes", label: t("internal.cta") }}
        />
        {error && <Failed />}
        {data && (
          <>
            <StatGrid className="xl:grid-cols-3 2xl:grid-cols-6">
              <StatCard icon={Inbox} label={t("dashboard.toQualify")} value={data.counts.to_qualify} />
              <StatCard icon={Layers} label={t("dashboard.inSourcing")} value={data.counts.in_sourcing} />
              <StatCard icon={ClipboardCheck} label={t("dashboard.proposalsOpen")} value={data.counts.proposals_open} />
              <StatCard icon={Package} label={t("dashboard.ordersActive")} value={data.counts.orders_active} />
              <StatCard icon={Truck} label={t("dashboard.deliveriesInTransit")} value={data.counts.deliveries_in_transit} />
              <StatCard icon={AlertCircle} label={t("dashboard.openClaims")} value={data.counts.open_claims} />
            </StatGrid>
            {data.money && (
              <StatGrid className="xl:grid-cols-2 2xl:grid-cols-2">
                <StatCard icon={Wallet} label={t("dashboard.revenue")} value={Number(data.money.revenue)} suffix="FCFA" />
                <StatCard icon={Percent} label={t("dashboard.margin")} value={Number(data.money.margin)} suffix="FCFA" />
              </StatGrid>
            )}
            <Card>
              <h2 className="mb-4 text-lg font-bold">{t("internal.byStep")}</h2>
              <ol className="flex flex-wrap items-stretch gap-2">
                {WORKFLOW.map(([field, key, Icon], index) => (
                  <li key={key} className="flex min-w-36 flex-1 items-center gap-2">
                    <div className="flex flex-1 items-center gap-3 rounded-control border border-border px-3 py-2.5">
                      <Icon className="size-5 shrink-0 text-primary-soft-foreground" aria-hidden />
                      <div>
                        <p className="text-xs text-muted-foreground">{t(`internal.${key}`)}</p>
                        <p className="tabular font-display text-lg font-extrabold">{format.number(data.workflow[field])}</p>
                      </div>
                    </div>
                    {index < WORKFLOW.length - 1 && <ChevronRight className="size-4 shrink-0 text-muted-foreground max-xl:hidden" aria-hidden />}
                  </li>
                ))}
              </ol>
            </Card>
            <div className="grid gap-5 xl:grid-cols-[3fr_2fr]">
              <SectionCard title={t("internal.inProgress")} href="/internal/demandes">
                {data.in_progress.length === 0 ? (
                  <p className="text-muted-foreground">{t("dashboard.nothingInProgress")}</p>
                ) : (
                  <DataTable
                    columns={[t("columns.reference"), t("columns.buyer"), t("columns.need"), t("columns.step"), t("columns.owner"), t("columns.date")]}
                    rows={data.in_progress.map((request) => ({
                      key: request.id,
                      cells: [
                        <span key="ref" className="tabular whitespace-nowrap font-medium">{request.reference}</span>,
                        request.buyer,
                        <span key="need">
                          <span className="font-semibold">{request.product}</span>
                          <span className="block text-xs text-muted-foreground">{quantity(request)}</span>
                        </span>,
                        <StatusBadge key="step" status={request.status} />,
                        request.assignee ?? "—",
                        <span key="date" className="text-muted-foreground">{day(request.created_at)}</span>,
                      ],
                    }))}
                  />
                )}
              </SectionCard>
              <div className="space-y-5">
                <SectionCard title={t("internal.requestsTrend")}>
                  <TrendChart points={data.trend} unit={t("internal.requestsUnit")} />
                </SectionCard>
                <SectionCard title={t("internal.activity")}>
                  {data.recent.length === 0 ? (
                    <p className="text-muted-foreground">{t("crm.noActivity")}</p>
                  ) : (
                    <ul className="space-y-4">
                      {data.recent.map((event) => (
                        <li key={`${event.kind}-${event.reference}`} className="flex items-baseline justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold">
                              {t(`dashboard.recent.${event.kind}`)} {event.reference}
                            </p>
                            <p className="text-sm text-muted-foreground">{event.party}</p>
                          </div>
                          <span className="shrink-0 text-xs text-muted-foreground">{format.relativeTime(new Date(event.at))}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </SectionCard>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
