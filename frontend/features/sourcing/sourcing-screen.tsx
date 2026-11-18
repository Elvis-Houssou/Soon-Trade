"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { useMe } from "@/components/auth/session";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DetailReveal } from "@/components/motion/motion";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage, SelectField, TextareaField } from "@/components/ui/field";
import { AVAILABILITY_TONE, type Product, useCategories } from "@/features/catalog/catalog-screens";
import { type PurchaseRequest, RequestFacts, StatusBadge, useQuantity } from "@/features/requests/shared";
import { CaseProposal } from "@/features/proposals/internal-proposals";
import { CaseSolicitations } from "@/features/solicitations/internal-solicitations";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";

type UserRef = { id: string; full_name: string };
type SupplierRef = { id: string; name: string; city: string | null };
type SourcingCase = {
  id: string;
  reference: string;
  created_at: string;
  request: PurchaseRequest;
  assignee: UserRef | null;
  candidates: { created_at: string; organization: SupplierRef }[];
  notes: { id: string; created_at: string; body: string; author: UserRef }[];
};
type SupplierProduct = {
  product_id: string;
  product_name: string;
  category_name: string;
  unit: string;
  packaging: string | null;
  available_quantity: string;
  availability: Product["availability"];
  supplier: SupplierRef;
};

const REFRESH = [["sourcing-cases"]];

function SupplierSearch({ sourcingCase, canManage }: { sourcingCase: SourcingCase; canManage: boolean }) {
  const t = useTranslations();
  const quantity = useQuantity();
  const categories = useCategories();
  // undefined = aucune recherche lancée.
  const [search, setSearch] = useState<string>();
  const results = useQuery({
    queryKey: ["sourcing-suppliers", search],
    queryFn: () => api<SupplierProduct[]>(`/sourcing/suppliers?${search}`),
    enabled: search !== undefined,
  });
  const add = useAction(
    (organization_id: string) => api(`/sourcing/cases/${sourcingCase.id}/candidates`, { organization_id }),
    REFRESH,
  );
  const shortlisted = new Set(sourcingCase.candidates.map((candidate) => candidate.organization.id));

  return (
    <div className="mt-6 border-t border-border pt-5">
      <h3 className="font-bold">{t("sourcing.search")}</h3>
      <p className="mb-3 text-sm text-muted-foreground">{t("sourcing.searchHint")}</p>
      <form
        className="grid items-end gap-4 md:grid-cols-[1fr_1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          const values = Object.entries(formValues(event.currentTarget)).filter(([, value]) => value);
          setSearch(new URLSearchParams(values).toString());
        }}
      >
        <Field name="q" label={t("sourcing.query")} maxLength={200} />
        <SelectField
          key={categories.data ? "loaded" : "loading"}
          name="category_id"
          label={t("requests.category")}
          defaultValue={sourcingCase.request.category_id ?? ""}
        >
          <option value="">{t("sourcing.allCategories")}</option>
          {categories.data?.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </SelectField>
        <Button type="submit" size="lg" className="h-11" variant="outline">
          {t("sourcing.searchSubmit")}
        </Button>
      </form>
      {(results.error || add.errorStatus !== undefined) && (
        <div className="mt-3">
          <FormMessage tone="error">{t("common.error")}</FormMessage>
        </div>
      )}
      {results.data && (
        <div className="mt-4">
          {results.data.length === 0 ? (
            <p className="text-muted-foreground">{t("sourcing.noResults")}</p>
          ) : (
            <DataTable
              columns={[t("columns.product"), t("sourcing.supplier"), t("catalog.stock"), t("catalog.availability"), ""]}
              rows={results.data.map((product) => ({
                key: product.product_id,
                cells: [
                  <span key="name">
                    <span className="font-semibold">{product.product_name}</span>
                    <span className="block text-muted-foreground">{product.category_name}</span>
                  </span>,
                  <span key="supplier">
                    {product.supplier.name}
                    {product.supplier.city && <span className="block text-muted-foreground">{product.supplier.city}</span>}
                  </span>,
                  <span key="stock" className="tabular whitespace-nowrap">
                    {quantity({ quantity: product.available_quantity, unit: product.unit })}
                  </span>,
                  <Badge key="availability" tone={AVAILABILITY_TONE[product.availability]}>
                    {t(`availability.${product.availability}`)}
                  </Badge>,
                  shortlisted.has(product.supplier.id) ? (
                    <Badge key="add" tone="success">{t("sourcing.shortlisted")}</Badge>
                  ) : canManage ? (
                    <Button key="add" variant="ghost" size="sm" disabled={add.pending} onClick={() => add.run(product.supplier.id)}>
                      {t("sourcing.shortlistAdd")}
                    </Button>
                  ) : null,
                ],
              }))}
            />
          )}
        </div>
      )}
    </div>
  );
}

function Details({ sourcingCase }: { sourcingCase: SourcingCase }) {
  const t = useTranslations();
  const format = useFormatter();
  const me = useMe().data;
  const canWrite = Boolean(me?.permissions.includes("sourcing:manage"));
  // Le dossier se fige quand la demande quitte l'état « en sourcing » ; les notes restent possibles.
  const active = sourcingCase.request.status === "in_sourcing";
  const canManage = canWrite && active;
  const path = `/sourcing/cases/${sourcingCase.id}`;
  const assignees = useQuery({
    queryKey: ["sourcing-assignees"],
    queryFn: () => api<UserRef[]>("/sourcing/assignees"),
    enabled: canManage,
  });
  const assign = useAction((assignee_id: string) => api(path, { assignee_id }, "PATCH"), REFRESH);
  const remove = useAction((id: string) => api(`${path}/candidates/${id}`, undefined, "DELETE"), REFRESH);
  const addNote = useAction((body: Record<string, string>) => api(`${path}/notes`, body), REFRESH);
  const failed = [assign, remove, addNote].some((action) => action.errorStatus !== undefined);

  return (
    <SectionCard title={`${sourcingCase.reference} · ${sourcingCase.request.buyer_name}`} action={<StatusBadge status={sourcingCase.request.status} />}>
      {!active && (
        <div className="mb-4">
          <FormMessage tone="error">{t("sourcing.frozen")}</FormMessage>
        </div>
      )}
      <p className="mb-3 text-sm text-muted-foreground">
        {t("sourcing.request")} {sourcingCase.request.reference}
      </p>
      <RequestFacts request={sourcingCase.request} />

      <div className="mt-6 border-t border-border pt-5">
        {canManage && assignees.data ? (
          <SelectField
            label={t("sourcing.assignee")}
            className="sm:max-w-xs"
            value={sourcingCase.assignee?.id ?? ""}
            disabled={assign.pending}
            onChange={(event) => event.target.value && assign.run(event.target.value)}
          >
            {!sourcingCase.assignee && <option value="">{t("sourcing.unassigned")}</option>}
            {assignees.data.map((user) => (
              <option key={user.id} value={user.id}>
                {user.full_name}
              </option>
            ))}
          </SelectField>
        ) : (
          <p>
            <span className="text-sm text-muted-foreground">{t("sourcing.assignee")} : </span>
            <span className="font-medium">{sourcingCase.assignee?.full_name ?? t("sourcing.unassigned")}</span>
          </p>
        )}
      </div>

      <div className="mt-6 border-t border-border pt-5">
        <h3 className="mb-3 font-bold">{t("sourcing.shortlist")}</h3>
        {sourcingCase.candidates.length === 0 ? (
          <p className="text-muted-foreground">{t("sourcing.noCandidates")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {sourcingCase.candidates.map(({ organization }) => (
              <li key={organization.id} className="flex items-center justify-between gap-3 py-2.5">
                <span>
                  <span className="font-semibold">{organization.name}</span>
                  {organization.city && <span className="text-muted-foreground"> · {organization.city}</span>}
                </span>
                {canManage && (
                  <Button variant="ghost" size="sm" disabled={remove.pending} onClick={() => remove.run(organization.id)}>
                    {t("sourcing.remove")}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {active && <SupplierSearch sourcingCase={sourcingCase} canManage={canManage} />}

      <CaseSolicitations
        caseId={sourcingCase.id}
        unit={sourcingCase.request.unit}
        candidates={sourcingCase.candidates}
        canManage={canManage}
      />

      <CaseProposal caseId={sourcingCase.id} active={active} />

      <div className="mt-6 border-t border-border pt-5">
        <h3 className="font-bold">{t("sourcing.notes")}</h3>
        <p className="mb-3 text-sm text-muted-foreground">{t("sourcing.notesHint")}</p>
        {sourcingCase.notes.length === 0 && <p className="text-muted-foreground">{t("sourcing.noNotes")}</p>}
        <ul className="space-y-3">
          {sourcingCase.notes.map((note) => (
            <li key={note.id} className="rounded-control bg-surface-muted px-3 py-2">
              <p className="whitespace-pre-line">{note.body}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {note.author.full_name} · {format.dateTime(new Date(note.created_at), { dateStyle: "medium", timeStyle: "short" })}
              </p>
            </li>
          ))}
        </ul>
        {canWrite && (
          <form
            className="mt-4 space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              const form = event.currentTarget;
              addNote.run(formValues(form), { onSuccess: () => form.reset() });
            }}
          >
            <TextareaField name="body" label={t("sourcing.note")} maxLength={4000} required />
            <Button type="submit" disabled={addNote.pending}>
              {t("sourcing.addNote")}
            </Button>
          </form>
        )}
      </div>
      {failed && (
        <div className="mt-3">
          <FormMessage tone="error">{t("common.error")}</FormMessage>
        </div>
      )}
    </SectionCard>
  );
}

/** Page interne « Sourcing » : dossiers ouverts à partir des demandes qualifiées. */
export function SourcingScreen() {
  const t = useTranslations();
  const [selectedId, setSelectedId] = useState<string>();
  const cases = useQuery({ queryKey: ["sourcing-cases"], queryFn: () => api<SourcingCase[]>("/sourcing/cases") });
  const selected = cases.data?.find((sourcingCase) => sourcingCase.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.sourcing")} description={t("sourcing.intro")} />
      {cases.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {cases.data && (
        <SectionCard title={t("sourcing.cases")}>
          {cases.data.length === 0 ? (
            <p className="text-muted-foreground">{t("sourcing.empty")}</p>
          ) : (
            <DataTable
              columns={[t("columns.reference"), t("columns.buyer"), t("columns.product"), t("sourcing.assignee"), t("columns.status"), ""]}
              rows={cases.data.map((sourcingCase) => ({
                key: sourcingCase.id,
                cells: [
                  <span key="reference" className="font-semibold whitespace-nowrap">{sourcingCase.reference}</span>,
                  sourcingCase.request.buyer_name,
                  sourcingCase.request.product_name,
                  sourcingCase.assignee?.full_name ?? t("sourcing.unassigned"),
                  <StatusBadge key="status" status={sourcingCase.request.status} />,
                  <Button
                    key="open"
                    variant="ghost"
                    size="sm"
                    aria-expanded={sourcingCase.id === selectedId}
                    onClick={() => setSelectedId(sourcingCase.id === selectedId ? undefined : sourcingCase.id)}
                  >
                    {t("sourcing.open")}
                  </Button>,
                ],
              }))}
            />
          )}
        </SectionCard>
      )}
      {selected && (
        <DetailReveal key={selected.id}>
          <Details key={selected.id} sourcingCase={selected} />
        </DetailReveal>
      )}
    </div>
  );
}
