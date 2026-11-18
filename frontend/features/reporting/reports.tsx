"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { ClipboardCheck, Download, FileText, Package, Percent, Send, Wallet } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { useMe } from "@/components/auth/session";
import { DataTable, PageHeading, StatCard, StatGrid } from "@/components/dashboard/widgets";
import { TrendChart } from "@/components/dashboard/trend-chart";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage } from "@/components/ui/field";
import { useMoney } from "@/features/solicitations/shared";
import { api, ApiError } from "@/lib/api";
import { formValues } from "@/lib/use-action";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const EXPORTS = ["requests", "orders", "deliveries", "claims"] as const;

type Report = {
  currency: string;
  funnel: { requests: number; proposals_sent: number; accepted: number; orders: number };
  rates: { proposal_rate: number | null; acceptance_rate: number | null };
  revenue: string;
  cost: string;
  margin: string;
  margin_rate: number | null;
  average_order: string | null;
  top_buyers: { name: string; amount: string }[];
  top_suppliers: { name: string; amount: string }[];
  monthly: { month: string; revenue: string; margin: string }[];
  open_claims: number;
};

/** Téléchargement par le navigateur : la session voyage dans le cookie, rien n'est stocké. */
async function download(kind: string) {
  const response = await fetch(`${API_URL}/internal/exports/${kind}`, { credentials: "include" });
  if (!response.ok) throw new ApiError(response.status, "export_failed");
  const blob = await response.blob();
  const name = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") ?? "")?.[1] ?? `${kind}.csv`;
  const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: name });
  link.click();
  URL.revokeObjectURL(link.href);
}

function Ranking({ title, rows, currency }: { title: string; rows: { name: string; amount: string }[]; currency: string }) {
  const t = useTranslations("reports");
  const money = useMoney();
  return (
    <SectionCard title={title}>
      {rows.length === 0 ? (
        <p className="text-muted-foreground">{t("noData")}</p>
      ) : (
        <ol className="space-y-2">
          {rows.map((row, index) => (
            <li key={row.name} className="flex items-baseline justify-between gap-3">
              <span>
                <span className="tabular mr-2 text-muted-foreground">{index + 1}.</span>
                <span className="font-semibold">{row.name}</span>
              </span>
              <span className="tabular whitespace-nowrap">{money(row.amount, currency)}</span>
            </li>
          ))}
        </ol>
      )}
    </SectionCard>
  );
}

/** Page interne « Rapports » : entonnoir, chiffre d'affaires, marge et exports autorisés. */
export function ReportsScreen() {
  const t = useTranslations();
  const format = useFormatter();
  const money = useMoney();
  const canExport = Boolean(useMe().data?.permissions.includes("report:export"));
  const [range, setRange] = useState<{ start?: string; end?: string }>({});
  const [exportError, setExportError] = useState(false);
  const query = new URLSearchParams(Object.entries(range).filter(([, v]) => v) as [string, string][]).toString();
  const report = useQuery({
    queryKey: ["report", query],
    queryFn: () => api<Report>(`/internal/reports/commercial${query ? `?${query}` : ""}`),
  });
  const percent = (value: number | null) => (value === null ? "—" : format.number(value, { style: "percent", maximumFractionDigits: 1 }));
  const data = report.data;

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.reports")} description={t("reports.intro")} />
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          setRange(formValues(event.currentTarget));
        }}
      >
        <Field name="start" type="date" label={t("reports.from")} />
        <Field name="end" type="date" label={t("reports.to")} />
        <Button type="submit" variant="outline" className="h-11">
          {t("reports.apply")}
        </Button>
      </form>
      {report.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {data && (
        <>
          <StatGrid className="xl:grid-cols-3 2xl:grid-cols-6">
            <StatCard icon={FileText} label={t("reports.requests")} value={data.funnel.requests} />
            <StatCard icon={Send} label={t("reports.proposalsSent")} value={data.funnel.proposals_sent} footnote={t("reports.rateOfRequests", { rate: percent(data.rates.proposal_rate) })} />
            <StatCard icon={ClipboardCheck} label={t("reports.accepted")} value={data.funnel.accepted} footnote={t("reports.rateOfSent", { rate: percent(data.rates.acceptance_rate) })} />
            <StatCard icon={Package} label={t("reports.orders")} value={data.funnel.orders} />
            <StatCard icon={Wallet} label={t("dashboard.revenue")} value={Number(data.revenue)} suffix="FCFA" />
            <StatCard icon={Percent} label={t("dashboard.margin")} value={Number(data.margin)} suffix="FCFA" footnote={percent(data.margin_rate)} />
          </StatGrid>
          <div className="grid gap-5 xl:grid-cols-[3fr_2fr]">
            <SectionCard title={t("reports.monthly")}>
              {data.monthly.length === 0 ? (
                <p className="text-muted-foreground">{t("reports.noData")}</p>
              ) : (
                <>
                  <TrendChart points={data.monthly.map((m) => ({ month: m.month, value: m.revenue }))} unit="FCFA" />
                  <DataTable
                    columns={[t("reports.month"), t("dashboard.revenue"), t("dashboard.margin")]}
                    rows={data.monthly.map((m) => ({
                      key: m.month,
                      cells: [
                        m.month,
                        <span key="r" className="tabular whitespace-nowrap">{money(m.revenue, data.currency)}</span>,
                        <span key="m" className="tabular whitespace-nowrap">{money(m.margin, data.currency)}</span>,
                      ],
                    }))}
                  />
                </>
              )}
            </SectionCard>
            <div className="space-y-5">
              <Ranking title={t("reports.topBuyers")} rows={data.top_buyers} currency={data.currency} />
              <Ranking title={t("reports.topSuppliers")} rows={data.top_suppliers} currency={data.currency} />
              <SectionCard title={t("reports.other")}>
                <p className="flex justify-between gap-3">
                  <span>{t("reports.averageOrder")}</span>
                  <span className="tabular font-semibold">{data.average_order ? money(data.average_order, data.currency) : "—"}</span>
                </p>
                <p className="mt-2 flex justify-between gap-3">
                  <span>{t("dashboard.openClaims")}</span>
                  <span className="tabular font-semibold">{data.open_claims}</span>
                </p>
              </SectionCard>
            </div>
          </div>
        </>
      )}
      {canExport && (
        <SectionCard title={t("reports.exports")}>
          <p className="mb-3 text-sm text-muted-foreground">{t("reports.exportsHint")}</p>
          <div className="flex flex-wrap gap-2">
            {EXPORTS.map((kind) => (
              <Button
                key={kind}
                variant="outline"
                size="sm"
                onClick={() => {
                  setExportError(false);
                  download(kind).catch(() => setExportError(true));
                }}
              >
                <Download className="size-4" aria-hidden />
                {t(`reports.exportKinds.${kind}`)}
              </Button>
            ))}
          </div>
          {exportError && (
            <div className="mt-3">
              <FormMessage tone="error">{t("common.error")}</FormMessage>
            </div>
          )}
        </SectionCard>
      )}
    </div>
  );
}

type AuditRow = { id: string; created_at: string; actor_name: string | null; action: string; subject: string; details: Record<string, unknown>; ip: string | null };
const PAGE = 50;

/** Page interne « Audit » : journal en lecture seule, filtrable, par pages de 50. */
export function AuditScreen() {
  const t = useTranslations();
  const format = useFormatter();
  const [filters, setFilters] = useState<{ action?: string; q?: string }>({});
  const audit = useInfiniteQuery({
    queryKey: ["audit", filters],
    initialPageParam: "",
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: String(PAGE) });
      if (filters.action) params.set("action", filters.action);
      if (filters.q) params.set("q", filters.q);
      if (pageParam) params.set("before", pageParam);
      return api<AuditRow[]>(`/audit?${params}`);
    },
    getNextPageParam: (last) => (last.length === PAGE ? last.at(-1)?.id : undefined),
  });
  const rows = audit.data?.pages.flat() ?? [];

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.audit")} description={t("audit.intro")} />
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          setFilters(formValues(event.currentTarget));
        }}
      >
        <Field name="action" label={t("audit.action")} hint={t("audit.actionHint")} maxLength={80} />
        <Field name="q" label={t("audit.subject")} maxLength={200} />
        <Button type="submit" variant="outline" className="h-11 self-start sm:mt-[1.875rem]">
          {t("reports.apply")}
        </Button>
      </form>
      {audit.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      <SectionCard title={t("audit.entries")}>
        {audit.data && rows.length === 0 ? (
          <p className="text-muted-foreground">{t("reports.noData")}</p>
        ) : (
          <DataTable
            columns={[t("columns.date"), t("audit.actor"), t("audit.action"), t("audit.subject"), t("audit.details")]}
            rows={rows.map((row) => ({
              key: row.id,
              cells: [
                <span key="date" className="whitespace-nowrap">{format.dateTime(new Date(row.created_at), { dateStyle: "short", timeStyle: "medium" })}</span>,
                row.actor_name ?? t("audit.system"),
                <code key="action" className="text-xs">{row.action}</code>,
                <span key="subject" className="break-all">{row.subject}</span>,
                <code key="details" className="block max-w-80 truncate text-xs text-muted-foreground" title={JSON.stringify(row.details)}>
                  {Object.keys(row.details).length ? JSON.stringify(row.details) : "—"}
                </code>,
              ],
            }))}
          />
        )}
        {audit.hasNextPage && (
          <div className="mt-4">
            <Button variant="outline" disabled={audit.isFetchingNextPage} onClick={() => audit.fetchNextPage()}>
              {t("audit.more")}
            </Button>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
