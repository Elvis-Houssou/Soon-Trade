"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { Button, ButtonLink } from "@/components/ui/button";
import { DetailReveal } from "@/components/motion/motion";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage, SelectField, TextareaField } from "@/components/ui/field";
import { useCategories } from "@/features/catalog/catalog-screens";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";
import { type PurchaseRequest, RequestFacts, RequestHistory, StatusBadge, useQuantity } from "./shared";

const UNITS = ["kg", "tonne", "litre", "sac", "carton", "unite"];
const CANCELLABLE = ["draft", "submitted", "info_requested", "qualified", "in_sourcing"];

/** Création ou modification d'une demande ; « Soumettre » enregistre puis soumet. */
function RequestForm({ request, onSaved }: { request?: PurchaseRequest; onSaved?: (submitted: boolean) => void }) {
  const t = useTranslations();
  const categories = useCategories();
  const replying = request?.status === "info_requested";
  const save = useAction(
    async ({ body, submit, message }: { body: Record<string, string | null>; submit: boolean; message?: string }) => {
      const saved = request
        ? await api<PurchaseRequest>(`/purchase-requests/${request.id}`, body, "PATCH")
        : await api<PurchaseRequest>("/purchase-requests", body);
      if (submit) await api(`/purchase-requests/${saved.id}/submit`, { message });
    },
    [["purchase-requests"]],
  );

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "submit";
        const { message, ...values } = formValues(form);
        const body = Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value || null]));
        save.run(
          { body, submit, message: message || undefined },
          {
            onSuccess: () => {
              if (!request) form.reset();
              onSaved?.(submit);
            },
          },
        );
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field name="product_name" label={t("requests.product")} defaultValue={request?.product_name} minLength={2} maxLength={200} required />
        {/* La clé remonte la liste quand les catégories arrivent : sans cela la valeur enregistrée ne serait pas présélectionnée. */}
        <SelectField
          key={categories.data ? "loaded" : "loading"}
          name="category_id"
          label={t("requests.category")}
          defaultValue={request?.category_id ?? ""}
        >
          <option value="">{t("requests.noCategory")}</option>
          {categories.data
            ?.filter((category) => category.is_active || category.id === request?.category_id)
            .map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
        </SelectField>
        <Field
          name="quantity"
          label={t("requests.quantity")}
          type="number"
          min={0.001}
          step="0.001"
          defaultValue={request ? Number(request.quantity) : undefined}
          required
        />
        <SelectField name="unit" label={t("requests.unit")} defaultValue={request?.unit ?? "tonne"}>
          {UNITS.map((unit) => (
            <option key={unit} value={unit}>
              {t(`units.${unit}`)}
            </option>
          ))}
        </SelectField>
        <Field name="packaging" label={t("requests.packaging")} defaultValue={request?.packaging ?? ""} maxLength={200} />
        <Field
          name="delivery_location"
          label={t("requests.deliveryLocation")}
          defaultValue={request?.delivery_location}
          minLength={2}
          maxLength={300}
          required
        />
        <Field name="desired_date" label={t("requests.desiredDate")} type="date" defaultValue={request?.desired_date ?? ""} />
      </div>
      <TextareaField name="specifications" label={t("requests.specifications")} defaultValue={request?.specifications ?? ""} maxLength={4000} />
      <TextareaField name="additional_info" label={t("requests.additionalInfo")} defaultValue={request?.additional_info ?? ""} maxLength={4000} />
      {replying && <TextareaField name="message" label={t("requests.reply")} hint={t("requests.replyHint")} maxLength={2000} />}
      {save.errorStatus !== undefined && (
        <FormMessage tone="error">{t(save.errorStatus === 409 ? "requests.conflict" : "common.error")}</FormMessage>
      )}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" value="submit" disabled={save.pending}>
          {t(replying ? "requests.sendReply" : "requests.submit")}
        </Button>
        <Button type="submit" value="draft" variant="outline" disabled={save.pending}>
          {t(replying ? "common.save" : "requests.saveDraft")}
        </Button>
      </div>
    </form>
  );
}

/** Page acheteur « Nouvelle demande ». */
export function NewRequestScreen() {
  const t = useTranslations();
  const [saved, setSaved] = useState<"draft" | "submitted">();

  return (
    <div className="space-y-5">
      <PageHeading title={t("requests.newTitle")} description={t("requests.newIntro")} />
      <SectionCard title={t("requests.newTitle")}>
        <RequestForm onSaved={(submitted) => setSaved(submitted ? "submitted" : "draft")} />
        {saved && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <FormMessage tone="success">{t(saved === "submitted" ? "requests.submittedDone" : "requests.draftSaved")}</FormMessage>
            <ButtonLink href="/buyer/demandes" variant="ghost" size="sm">
              {t("nav.requests")}
            </ButtonLink>
          </div>
        )}
      </SectionCard>
    </div>
  );
}

function Details({ request }: { request: PurchaseRequest }) {
  const t = useTranslations();
  const editable = request.status === "draft" || request.status === "info_requested";
  const cancel = useAction(() => api(`/purchase-requests/${request.id}/cancel`, {}), [["purchase-requests"]]);

  return (
    <SectionCard
      title={`${request.reference} · ${request.product_name}`}
      action={
        CANCELLABLE.includes(request.status) ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={cancel.pending}
            onClick={() => {
              if (window.confirm(t("requests.cancelConfirm"))) cancel.run();
            }}
          >
            {t("requests.cancel")}
          </Button>
        ) : undefined
      }
    >
      {cancel.errorStatus !== undefined && <FormMessage tone="error">{t("common.error")}</FormMessage>}
      {request.status === "info_requested" && (
        <div className="mb-4 rounded-control bg-warning-soft px-3 py-2 text-warning-foreground">
          <p className="text-sm font-semibold">{t("requestStatus.info_requested")}</p>
          <p className="whitespace-pre-line">{request.history.at(-1)?.message}</p>
        </div>
      )}
      {["proposal_sent", "accepted"].includes(request.status) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-control bg-primary-soft px-3 py-2 text-primary-soft-foreground">
          <p className="text-sm font-semibold">{t(request.status === "accepted" ? "proposals.requestAccepted" : "proposals.requestWaiting")}</p>
          <ButtonLink href="/buyer/propositions" variant="ghost" size="sm">
            {t("proposals.see")}
          </ButtonLink>
        </div>
      )}
      {editable ? <RequestForm key={request.status} request={request} /> : <RequestFacts request={request} />}
      <RequestHistory history={request.history} />
    </SectionCard>
  );
}

/** Page acheteur « Mes demandes ». */
export function BuyerRequestsScreen() {
  const t = useTranslations();
  const format = useFormatter();
  const quantity = useQuantity();
  const [selectedId, setSelectedId] = useState<string>();
  const requests = useQuery({
    queryKey: ["purchase-requests"],
    queryFn: () => api<PurchaseRequest[]>("/purchase-requests"),
  });
  const selected = requests.data?.find((request) => request.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.requests")} description={t("requests.mineIntro")} />
      {requests.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {requests.data && (
        <SectionCard
          title={t("nav.requests")}
          action={
            <ButtonLink href="/buyer/nouvelle-demande" size="sm" className="shadow-none">
              {t("nav.newRequest")}
            </ButtonLink>
          }
        >
          {requests.data.length === 0 ? (
            <p className="text-muted-foreground">{t("requests.empty")}</p>
          ) : (
            <DataTable
              columns={[t("columns.reference"), t("columns.product"), t("columns.quantity"), t("columns.status"), t("columns.date"), ""]}
              rows={requests.data.map((request) => ({
                key: request.id,
                cells: [
                  <span key="reference" className="font-semibold whitespace-nowrap">{request.reference}</span>,
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
