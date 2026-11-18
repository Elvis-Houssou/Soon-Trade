"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { Button, ButtonLink } from "@/components/ui/button";
import { DetailReveal } from "@/components/motion/motion";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage, TextareaField } from "@/components/ui/field";
import { useQuantity } from "@/features/requests/shared";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";
import { NeedFacts, OfferBadge, OfferFacts, type Solicitation, SolicitationBadge, useDay, useMoney } from "./shared";

type OwnDocument = { id: string; filename: string; doc_type: string };

const REFRESH = [["solicitations"]];

function OfferForm({ solicitation, onDone }: { solicitation: Solicitation; onDone: () => void }) {
  const t = useTranslations();
  const current = solicitation.offer?.versions.at(-1);
  const documents = useQuery({ queryKey: ["documents"], queryFn: () => api<OwnDocument[]>("/documents") });
  const save = useAction(
    (body: Record<string, unknown>) =>
      api(`/solicitations/${solicitation.id}/offer`, body, solicitation.offer ? "PUT" : "POST"),
    REFRESH,
  );
  const attached = new Set(current?.attachments.map((attachment) => attachment.id));

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const values = formValues(form);
        const attachment_ids = new FormData(form).getAll("attachment_ids").map(String);
        save.run(
          {
            unit_price: values.unit_price,
            quantity: values.quantity,
            lead_time_days: Number(values.lead_time_days),
            valid_until: values.valid_until,
            packaging: values.packaging || null,
            conditions: values.conditions || null,
            attachment_ids,
          },
          { onSuccess: onDone },
        );
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          name="unit_price"
          label={t("offers.unitPriceInput", { unit: t(`units.${solicitation.unit}`).toLowerCase() })}
          type="number"
          min={0.01}
          step="0.01"
          defaultValue={current ? Number(current.unit_price) : undefined}
          required
        />
        <Field
          name="quantity"
          label={t("offers.quantity")}
          hint={t("offers.quantityHint")}
          type="number"
          min={0.001}
          step="0.001"
          defaultValue={Number(current?.quantity ?? solicitation.quantity)}
          required
        />
        <Field
          name="lead_time_days"
          label={t("offers.leadTimeInput")}
          type="number"
          min={0}
          max={365}
          step="1"
          defaultValue={current?.lead_time_days}
          required
        />
        <Field name="valid_until" label={t("offers.validUntil")} type="date" defaultValue={current?.valid_until} required />
        <Field name="packaging" label={t("requests.packaging")} defaultValue={current?.packaging ?? solicitation.packaging ?? ""} maxLength={200} />
      </div>
      <TextareaField name="conditions" label={t("offers.conditions")} hint={t("offers.conditionsHint")} defaultValue={current?.conditions ?? ""} maxLength={4000} />

      <fieldset>
        <legend className="mb-1.5 text-sm font-semibold">{t("offers.attachments")}</legend>
        {documents.data?.length ? (
          <ul className="space-y-1">
            {documents.data.map((document) => (
              <li key={document.id}>
                <label className="flex items-center gap-2">
                  <input type="checkbox" name="attachment_ids" value={document.id} defaultChecked={attached.has(document.id)} className="size-4" />
                  <span>
                    {document.filename} <span className="text-sm text-muted-foreground">· {t(`documents.${document.doc_type}`)}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t("offers.noDocuments")}</p>
        )}
        <ButtonLink href="/supplier/profil" variant="ghost" size="sm" className="mt-1 px-0">
          {t("offers.uploadDocument")}
        </ButtonLink>
      </fieldset>

      {save.errorStatus !== undefined && (
        <FormMessage tone="error">
          {t(save.errorStatus === 409 ? "offers.conflict" : save.errorStatus === 400 ? "offers.invalid" : "common.error")}
        </FormMessage>
      )}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={save.pending}>
          {t(solicitation.offer ? "offers.saveRevision" : "offers.submit")}
        </Button>
        {solicitation.offer && (
          <Button variant="outline" disabled={save.pending} onClick={onDone}>
            {t("common.cancel")}
          </Button>
        )}
      </div>
    </form>
  );
}

function DeclineForm({ solicitation }: { solicitation: Solicitation }) {
  const t = useTranslations();
  const [open, setOpen] = useState(false);
  const decline = useAction(
    (body: Record<string, string>) => api(`/solicitations/${solicitation.id}/decline`, body),
    REFRESH,
  );
  if (!open)
    return (
      <Button variant="ghost" onClick={() => setOpen(true)}>
        {t("solicitations.decline")}
      </Button>
    );
  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        decline.run(formValues(event.currentTarget));
      }}
    >
      <TextareaField name="message" label={t("solicitations.declineReason")} maxLength={2000} />
      {decline.errorStatus !== undefined && <FormMessage tone="error">{t("offers.conflict")}</FormMessage>}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" variant="outline" disabled={decline.pending}>
          {t("solicitations.confirmDecline")}
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          {t("common.cancel")}
        </Button>
      </div>
    </form>
  );
}

function Details({ id }: { id: string }) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const [revising, setRevising] = useState(false);
  // Ouvrir la sollicitation la marque « consultée » côté SOON TRADE.
  const detail = useQuery({
    queryKey: ["solicitations", id],
    queryFn: async () => {
      const solicitation = await api<Solicitation>(`/solicitations/${id}`);
      void queryClient.invalidateQueries({ queryKey: ["solicitations"], exact: true });
      return solicitation;
    },
  });
  const withdraw = useAction(() => api(`/solicitations/${id}/offer/withdraw`, {}), REFRESH);
  const solicitation = detail.data;
  if (!solicitation) return detail.error ? <FormMessage tone="error">{t("common.error")}</FormMessage> : null;
  const open = solicitation.status === "sent" || solicitation.status === "viewed";
  const offer = solicitation.offer;

  return (
    <SectionCard title={`${solicitation.reference} · ${solicitation.product_name}`} action={<SolicitationBadge status={solicitation.status} />}>
      <NeedFacts solicitation={solicitation} />

      <div className="mt-6 border-t border-border pt-5">
        <h3 className="mb-3 font-bold">{t("offers.yourOffer")}</h3>
        {offer && !revising && (
          <>
            <OfferFacts offer={offer} unit={solicitation.unit} />
            {offer.status === "submitted" && (
              <div className="mt-4 flex flex-wrap gap-3">
                <Button variant="outline" onClick={() => setRevising(true)}>
                  {t("offers.revise")}
                </Button>
                <Button
                  variant="ghost"
                  disabled={withdraw.pending}
                  onClick={() => {
                    if (window.confirm(t("offers.withdrawConfirm"))) withdraw.run();
                  }}
                >
                  {t("offers.withdraw")}
                </Button>
              </div>
            )}
            {withdraw.errorStatus !== undefined && <FormMessage tone="error">{t("offers.conflict")}</FormMessage>}
          </>
        )}
        {(revising || (!offer && open)) && (
          <OfferForm solicitation={solicitation} onDone={() => setRevising(false)} />
        )}
        {!offer && !open && <p className="text-muted-foreground">{t("offers.closed")}</p>}
        {solicitation.decline_reason && <p className="mt-2 whitespace-pre-line">{solicitation.decline_reason}</p>}
      </div>

      {!offer && open && (
        <div className="mt-6 border-t border-border pt-5">
          <DeclineForm solicitation={solicitation} />
        </div>
      )}
    </SectionCard>
  );
}

/** Pages fournisseur « Sollicitations » et « Mes offres » (seulement celles auxquelles il a répondu). */
export function SupplierSolicitationsScreen({ offersOnly = false }: { offersOnly?: boolean }) {
  const t = useTranslations();
  const quantity = useQuantity();
  const money = useMoney();
  const day = useDay();
  const [selectedId, setSelectedId] = useState<string>();
  const solicitations = useQuery({ queryKey: ["solicitations"], queryFn: () => api<Solicitation[]>("/solicitations") });
  const rows = solicitations.data?.filter((solicitation) => !offersOnly || solicitation.offer);
  const title = t(offersOnly ? "nav.offers" : "nav.solicitations");

  return (
    <div className="space-y-5">
      <PageHeading title={title} description={t(offersOnly ? "offers.mineIntro" : "solicitations.supplierIntro")} />
      {solicitations.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {rows && (
        <SectionCard title={title}>
          {rows.length === 0 ? (
            <p className="text-muted-foreground">{t(offersOnly ? "offers.empty" : "solicitations.empty")}</p>
          ) : (
            <DataTable
              columns={[
                t("columns.reference"),
                t("columns.product"),
                t("columns.quantity"),
                offersOnly ? t("offers.unitPrice") : t("solicitations.deadline"),
                t("columns.status"),
                "",
              ]}
              rows={rows.map((solicitation) => {
                const current = solicitation.offer?.versions.at(-1);
                return {
                  key: solicitation.id,
                  cells: [
                    <span key="reference" className="font-semibold whitespace-nowrap">
                      {offersOnly ? solicitation.offer?.reference : solicitation.reference}
                    </span>,
                    solicitation.product_name,
                    <span key="quantity" className="tabular whitespace-nowrap">{quantity(solicitation)}</span>,
                    <span key="third" className="tabular whitespace-nowrap">
                      {offersOnly && current ? money(current.unit_price, current.currency) : day(solicitation.response_deadline)}
                    </span>,
                    offersOnly && solicitation.offer ? (
                      <OfferBadge key="status" status={solicitation.offer.status} />
                    ) : (
                      <SolicitationBadge key="status" status={solicitation.status} />
                    ),
                    <Button
                      key="open"
                      variant="ghost"
                      size="sm"
                      aria-expanded={solicitation.id === selectedId}
                      onClick={() => setSelectedId(solicitation.id === selectedId ? undefined : solicitation.id)}
                    >
                      {t("solicitations.open")}
                    </Button>,
                  ],
                };
              })}
            />
          )}
        </SectionCard>
      )}
      {selectedId && (
        <DetailReveal key={selectedId}>
          <Details key={selectedId} id={selectedId} />
        </DetailReveal>
      )}
    </div>
  );
}
