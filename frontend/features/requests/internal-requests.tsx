"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { useMe } from "@/components/auth/session";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { Button, ButtonLink } from "@/components/ui/button";
import { DetailReveal } from "@/components/motion/motion";
import { SectionCard } from "@/components/ui/card";
import { FormMessage, TextareaField } from "@/components/ui/field";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";
import { type PurchaseRequest, RequestFacts, RequestHistory, StatusBadge, useQuantity } from "./shared";

const ACTIONS = ["qualify", "request-info", "reject"] as const;
const REFRESH = [["internal-purchase-requests"], ["sourcing-cases"]];

function Details({ request }: { request: PurchaseRequest }) {
  const t = useTranslations();
  const me = useMe().data;
  const canQualify = request.status === "submitted" && me?.permissions.includes("purchase_request:qualify");
  const canOpenCase = request.status === "qualified" && me?.permissions.includes("sourcing:manage");
  const act = useAction(
    ({ action, message }: { action: string; message: string }) =>
      api(`/internal/purchase-requests/${request.id}/${action}`, action === "qualify" ? {} : { message }),
    REFRESH,
  );
  const openCase = useAction(() => api("/sourcing/cases", { request_id: request.id }), REFRESH);
  const errorStatus = act.errorStatus ?? openCase.errorStatus;

  return (
    <SectionCard title={`${request.reference} · ${request.buyer_name}`}>
      <RequestFacts request={request} />

      {canQualify && (
        <form
          className="mt-6 space-y-4 border-t border-border pt-5"
          onSubmit={(event) => {
            event.preventDefault();
            const action = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") ?? "qualify";
            act.run({ action, message: formValues(event.currentTarget).message });
          }}
        >
          <h3 className="font-bold">{t("requests.qualification")}</h3>
          <TextareaField name="message" label={t("requests.message")} hint={t("requests.messageHint")} maxLength={2000} />
          <div className="flex flex-wrap gap-3">
            {ACTIONS.map((action) => (
              <Button key={action} type="submit" value={action} variant={action === "qualify" ? "primary" : "outline"} disabled={act.pending}>
                {t(`requests.actions.${action}`)}
              </Button>
            ))}
          </div>
        </form>
      )}

      {canOpenCase && (
        <div className="mt-6 border-t border-border pt-5">
          <Button disabled={openCase.pending} onClick={() => openCase.run()}>
            {t("requests.openCase")}
          </Button>
        </div>
      )}

      {request.status === "in_sourcing" && me?.permissions.includes("sourcing:read") && (
        <div className="mt-6 border-t border-border pt-5">
          <ButtonLink href="/internal/sourcing" variant="outline">
            {t("requests.goToSourcing")}
          </ButtonLink>
        </div>
      )}

      {errorStatus !== undefined && (
        <div className="mt-3">
          <FormMessage tone="error">
            {t(errorStatus === 422 ? "requests.messageRequired" : errorStatus === 409 ? "requests.conflict" : "common.error")}
          </FormMessage>
        </div>
      )}
      <RequestHistory history={request.history} />
    </SectionCard>
  );
}

/** Page interne « Demandes acheteurs ». */
export function InternalRequestsScreen() {
  const t = useTranslations();
  const format = useFormatter();
  const quantity = useQuantity();
  const [selectedId, setSelectedId] = useState<string>();
  const requests = useQuery({
    queryKey: ["internal-purchase-requests"],
    queryFn: () => api<PurchaseRequest[]>("/internal/purchase-requests"),
  });
  const selected = requests.data?.find((request) => request.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.buyerRequests")} description={t("requests.allIntro")} />
      {requests.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {requests.data && (
        <SectionCard title={t("nav.buyerRequests")}>
          {requests.data.length === 0 ? (
            <p className="text-muted-foreground">{t("requests.emptyInternal")}</p>
          ) : (
            <DataTable
              columns={[
                t("columns.reference"),
                t("columns.buyer"),
                t("columns.product"),
                t("columns.quantity"),
                t("columns.status"),
                t("columns.date"),
                "",
              ]}
              rows={requests.data.map((request) => ({
                key: request.id,
                cells: [
                  <span key="reference" className="font-semibold whitespace-nowrap">{request.reference}</span>,
                  request.buyer_name,
                  request.product_name,
                  <span key="quantity" className="tabular whitespace-nowrap">{quantity(request)}</span>,
                  <StatusBadge key="status" status={request.status} />,
                  format.dateTime(new Date(request.created_at), { dateStyle: "medium" }),
                  <Button
                    key="open"
                    variant="ghost"
                    size="sm"
                    aria-expanded={request.id === selectedId}
                    onClick={() => setSelectedId(request.id === selectedId ? undefined : request.id)}
                  >
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
          <Details key={selected.id} request={selected} />
        </DetailReveal>
      )}
    </div>
  );
}
