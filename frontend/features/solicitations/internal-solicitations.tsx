"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useMe } from "@/components/auth/session";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage, SelectField, TextareaField } from "@/components/ui/field";
import { useQuantity } from "@/features/requests/shared";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";
import { Attachments, type InternalSolicitation, OfferBadge, SolicitationBadge, useDay, useMoney } from "./shared";

const UNITS = ["kg", "tonne", "litre", "sac", "carton", "unite"];
// Offres encore en lice pour la comparaison.
const IN_PLAY = ["submitted", "under_review", "retained"];
const DECISIONS = { submitted: ["review"], under_review: ["retain", "reject"] } as Record<string, string[]>;

/** Relecture du brouillon avant l'envoi : c'est ce texte, et lui seul, que lira le fournisseur. */
function DraftForm({ solicitation, refresh, onClose }: { solicitation: InternalSolicitation; refresh: string[][]; onClose: () => void }) {
  const t = useTranslations();
  const save = useAction(async ({ body, send }: { body: Record<string, string | null>; send: boolean }) => {
    await api(`/sourcing/solicitations/${solicitation.id}`, body, "PATCH");
    if (send) await api(`/sourcing/solicitations/${solicitation.id}/send`, {});
  }, refresh);

  return (
    <form
      className="space-y-4 rounded-control border border-border p-4"
      onSubmit={(event) => {
        event.preventDefault();
        const send = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "send";
        const values = Object.entries(formValues(event.currentTarget));
        save.run({ body: Object.fromEntries(values.map(([key, value]) => [key, value || null])), send }, { onSuccess: onClose });
      }}
    >
      <p className="text-sm text-muted-foreground">{t("solicitations.draftHint", { supplier: solicitation.supplier_name })}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field name="product_name" label={t("requests.product")} defaultValue={solicitation.product_name} minLength={2} maxLength={200} required />
        <Field name="quantity" label={t("requests.quantity")} type="number" min={0.001} step="0.001" defaultValue={Number(solicitation.quantity)} required />
        <SelectField name="unit" label={t("requests.unit")} defaultValue={solicitation.unit}>
          {UNITS.map((unit) => (
            <option key={unit} value={unit}>
              {t(`units.${unit}`)}
            </option>
          ))}
        </SelectField>
        <Field name="packaging" label={t("requests.packaging")} defaultValue={solicitation.packaging ?? ""} maxLength={200} />
        <Field name="delivery_location" label={t("requests.deliveryLocation")} defaultValue={solicitation.delivery_location} minLength={2} maxLength={300} required />
        <Field name="desired_date" label={t("requests.desiredDate")} type="date" defaultValue={solicitation.desired_date ?? ""} />
        <Field name="response_deadline" label={t("solicitations.deadline")} type="date" defaultValue={solicitation.response_deadline} required />
      </div>
      <TextareaField name="specifications" label={t("requests.specifications")} defaultValue={solicitation.specifications ?? ""} maxLength={4000} />
      <TextareaField name="message" label={t("solicitations.message")} hint={t("solicitations.messageHint")} defaultValue={solicitation.message ?? ""} maxLength={2000} />
      {save.errorStatus !== undefined && (
        <FormMessage tone="error">
          {t(save.errorStatus === 400 ? "solicitations.sendRefused" : save.errorStatus === 409 ? "requests.conflict" : "common.error")}
        </FormMessage>
      )}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" value="send" disabled={save.pending}>
          {t("solicitations.send")}
        </Button>
        <Button type="submit" value="save" variant="outline" disabled={save.pending}>
          {t("common.save")}
        </Button>
        <Button variant="ghost" disabled={save.pending} onClick={onClose}>
          {t("common.cancel")}
        </Button>
      </div>
    </form>
  );
}

/** Comparaison interne : jamais montrée à un fournisseur ni à l'acheteur. */
function Comparison({ solicitations, unit, canManage, refresh }: { solicitations: InternalSolicitation[]; unit: string; canManage: boolean; refresh: string[][] }) {
  const t = useTranslations();
  const money = useMoney();
  const quantity = useQuantity();
  const day = useDay();
  const decide = useAction(({ id, action }: { id: string; action: string }) => api(`/sourcing/offers/${id}/${action}`, {}), refresh);
  const offers = solicitations
    .flatMap((solicitation) => {
      const current = solicitation.offer?.versions.at(-1);
      return solicitation.offer && current ? [{ solicitation, offer: solicitation.offer, current }] : [];
    })
    .sort((a, b) => Number(a.current.unit_price) - Number(b.current.unit_price));
  const best = offers.find(({ offer }) => IN_PLAY.includes(offer.status));

  return (
    <div className="mt-6 border-t border-border pt-5">
      <h3 className="font-bold">{t("offers.comparison")}</h3>
      <p className="mb-3 text-sm text-muted-foreground">{t("offers.comparisonHint")}</p>
      {offers.length === 0 ? (
        <p className="text-muted-foreground">{t("offers.noneYet")}</p>
      ) : (
        <DataTable
          columns={[t("sourcing.supplier"), t("offers.unitPrice"), t("offers.quantity"), t("offers.total"), t("offers.leadTime"), t("offers.validUntil"), t("columns.status"), ""]}
          rows={offers.map(({ solicitation, offer, current }) => ({
            key: offer.id,
            cells: [
              <span key="supplier">
                <span className="font-semibold">{solicitation.supplier_name}</span>
                <span className="block text-muted-foreground">
                  {offer.reference} · {t("offers.version", { version: current.version })}
                </span>
                {current.conditions && <span className="block whitespace-pre-line text-muted-foreground">{current.conditions}</span>}
                {current.attachments.length > 0 && <Attachments attachments={current.attachments} />}
              </span>,
              <span key="price" className="tabular whitespace-nowrap">
                {money(current.unit_price, current.currency)}
                {offer === best?.offer && (
                  <Badge tone="success" className="mt-1 flex w-fit">
                    {t("offers.bestPrice")}
                  </Badge>
                )}
              </span>,
              <span key="quantity" className="tabular whitespace-nowrap">{quantity({ quantity: current.quantity, unit })}</span>,
              <span key="total" className="tabular whitespace-nowrap">{money(current.total, current.currency)}</span>,
              t("offers.days", { count: current.lead_time_days }),
              day(current.valid_until),
              <OfferBadge key="status" status={offer.status} />,
              <span key="actions" className="flex flex-wrap gap-1">
                {canManage &&
                  (DECISIONS[offer.status] ?? []).map((action) => (
                    <Button key={action} variant="ghost" size="sm" disabled={decide.pending} onClick={() => decide.run({ id: offer.id, action })}>
                      {t(`offers.actions.${action}`)}
                    </Button>
                  ))}
              </span>,
            ],
          }))}
        />
      )}
      {decide.errorStatus !== undefined && <FormMessage tone="error">{t("requests.conflict")}</FormMessage>}
    </div>
  );
}

/** Section « Sollicitations et offres » d'un dossier de sourcing. */
export function CaseSolicitations({
  caseId,
  unit,
  candidates,
  canManage,
}: {
  caseId: string;
  unit: string;
  candidates: { organization: { id: string; name: string } }[];
  canManage: boolean;
}) {
  const t = useTranslations();
  const day = useDay();
  const refresh = [["case-solicitations", caseId], ["internal-solicitations"]];
  const [editingId, setEditingId] = useState<string>();
  const solicitations = useQuery({
    queryKey: ["case-solicitations", caseId],
    queryFn: () => api<InternalSolicitation[]>(`/sourcing/cases/${caseId}/solicitations`),
  });
  const prepare = useAction((organization_id: string) => api<InternalSolicitation>(`/sourcing/cases/${caseId}/solicitations`, { organization_id }), refresh);
  const cancel = useAction((id: string) => api(`/sourcing/solicitations/${id}/cancel`, {}), refresh);
  const byOrganization = new Map(solicitations.data?.map((solicitation) => [solicitation.organization_id, solicitation]));
  // Une sollicitation reste listée même si son fournisseur a été retiré de la présélection.
  const suppliers = [
    ...candidates.map(({ organization }) => organization),
    ...(solicitations.data ?? [])
      .filter((solicitation) => !candidates.some(({ organization }) => organization.id === solicitation.organization_id))
      .map((solicitation) => ({ id: solicitation.organization_id, name: solicitation.supplier_name })),
  ];
  const editing = solicitations.data?.find((solicitation) => solicitation.id === editingId);

  return (
    <>
      <div className="mt-6 border-t border-border pt-5">
        <h3 className="font-bold">{t("solicitations.title")}</h3>
        <p className="mb-3 text-sm text-muted-foreground">{t("solicitations.internalHint")}</p>
        {suppliers.length === 0 ? (
          <p className="text-muted-foreground">{t("sourcing.noCandidates")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {suppliers.map((supplier) => {
              const solicitation = byOrganization.get(supplier.id);
              return (
                <li key={supplier.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                  <span>
                    <span className="font-semibold">{supplier.name}</span>
                    {solicitation && (
                      <span className="block text-sm text-muted-foreground">
                        {solicitation.reference} · {t("solicitations.deadlineOn", { date: day(solicitation.response_deadline) })}
                      </span>
                    )}
                    {solicitation?.decline_reason && <span className="block whitespace-pre-line text-sm">{solicitation.decline_reason}</span>}
                  </span>
                  <span className="flex flex-wrap items-center gap-2">
                    {solicitation ? <SolicitationBadge status={solicitation.status} /> : <Badge>{t("solicitations.notSolicited")}</Badge>}
                    {canManage && !solicitation && (
                      <Button variant="ghost" size="sm" disabled={prepare.pending} onClick={() => prepare.run(supplier.id, { onSuccess: (created) => setEditingId((created as InternalSolicitation).id) })}>
                        {t("solicitations.prepare")}
                      </Button>
                    )}
                    {canManage && solicitation?.status === "draft" && (
                      <Button variant="ghost" size="sm" onClick={() => setEditingId(solicitation.id)}>
                        {t("solicitations.review")}
                      </Button>
                    )}
                    {canManage && solicitation && ["draft", "sent", "viewed", "expired"].includes(solicitation.status) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={cancel.pending}
                        onClick={() => {
                          if (window.confirm(t("solicitations.cancelConfirm"))) cancel.run(solicitation.id);
                        }}
                      >
                        {t("solicitations.cancel")}
                      </Button>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        {(prepare.errorStatus ?? cancel.errorStatus) !== undefined && (
          <FormMessage tone="error">{t(prepare.errorStatus === 400 ? "solicitations.sendRefused" : "requests.conflict")}</FormMessage>
        )}
        {editing?.status === "draft" && canManage && <DraftForm key={editing.id} solicitation={editing} refresh={refresh} onClose={() => setEditingId(undefined)} />}
      </div>
      {solicitations.data && <Comparison solicitations={solicitations.data} unit={unit} canManage={canManage} refresh={refresh} />}
    </>
  );
}

/** Pages internes « Sollicitations » et « Offres reçues » : vue d'ensemble, l'action se fait dans le dossier. */
export function InternalSolicitationsScreen({ offersOnly = false }: { offersOnly?: boolean }) {
  const t = useTranslations();
  const me = useMe().data;
  const money = useMoney();
  const day = useDay();
  const solicitations = useQuery({
    queryKey: ["internal-solicitations"],
    queryFn: () => api<InternalSolicitation[]>("/sourcing/solicitations"),
  });
  const rows = solicitations.data?.filter((solicitation) => !offersOnly || solicitation.offer);
  const title = t(offersOnly ? "nav.receivedOffers" : "nav.solicitations");

  return (
    <div className="space-y-5">
      <PageHeading title={title} description={t(offersOnly ? "offers.internalIntro" : "solicitations.allIntro")} />
      {solicitations.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {rows && (
        <SectionCard
          title={title}
          action={
            me?.permissions.includes("sourcing:read") ? (
              <ButtonLink href="/internal/sourcing" variant="ghost" size="sm">
                {t("requests.goToSourcing")}
              </ButtonLink>
            ) : undefined
          }
        >
          {rows.length === 0 ? (
            <p className="text-muted-foreground">{t(offersOnly ? "offers.noneYet" : "solicitations.emptyInternal")}</p>
          ) : (
            <DataTable
              columns={[
                t("columns.reference"),
                t("sourcing.supplier"),
                t("solicitations.case"),
                t("columns.product"),
                offersOnly ? t("offers.unitPrice") : t("solicitations.deadline"),
                t("columns.status"),
              ]}
              rows={rows.map((solicitation) => {
                const current = solicitation.offer?.versions.at(-1);
                return {
                  key: solicitation.id,
                  cells: [
                    <span key="reference" className="font-semibold whitespace-nowrap">
                      {offersOnly ? solicitation.offer?.reference : solicitation.reference}
                    </span>,
                    solicitation.supplier_name,
                    <span key="case" className="whitespace-nowrap">{solicitation.case_reference}</span>,
                    solicitation.product_name,
                    <span key="third" className="tabular whitespace-nowrap">
                      {offersOnly && current ? money(current.unit_price, current.currency) : day(solicitation.response_deadline)}
                    </span>,
                    offersOnly && solicitation.offer ? (
                      <OfferBadge key="status" status={solicitation.offer.status} />
                    ) : (
                      <SolicitationBadge key="status" status={solicitation.status} />
                    ),
                  ],
                };
              })}
            />
          )}
        </SectionCard>
      )}
    </div>
  );
}
