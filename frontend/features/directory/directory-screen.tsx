"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useMe } from "@/components/auth/session";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DetailReveal } from "@/components/motion/motion";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage, SelectField, TextareaField } from "@/components/ui/field";
import { type Product, ProductTable, useCategories } from "@/features/catalog/catalog-screens";
import { OrganizationDocuments } from "@/features/documents/documents";
import { type Organization, VERIFICATION_TONE } from "@/features/organization/organization-screens";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";

type Kind = "buyer" | "supplier";
type DirectoryEntry = Organization & { verification_note: string | null };

const STATUSES = ["pending", "verified", "rejected", "suspended"] as const;

function CreateForm({ kind }: { kind: Kind }) {
  const t = useTranslations();
  const [invited, setInvited] = useState<string>();
  const create = useAction(
    (body: Record<string, string>) => api("/organizations", { ...body, kind }),
    [["organizations", kind]],
  );

  return (
    <SectionCard title={t(kind === "buyer" ? "directory.createBuyer" : "directory.createSupplier")}>
      <form
        className="grid items-end gap-4 md:grid-cols-[1fr_1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const values = formValues(form);
          create.run(values, {
            onSuccess: () => {
              setInvited(values.owner_email);
              form.reset();
            },
          });
        }}
      >
        <Field name="name" label={t("directory.orgName")} minLength={2} maxLength={200} required />
        <Field name="owner_email" type="email" label={t("directory.ownerEmail")} required />
        <Button type="submit" size="lg" className="h-11" disabled={create.pending}>
          {t("directory.createSubmit")}
        </Button>
      </form>
      <div className="mt-3">
        {create.done && invited && <FormMessage tone="success">{t("directory.created", { email: invited })}</FormMessage>}
        {create.errorStatus !== undefined && (
          <FormMessage tone="error">{t(create.errorStatus === 409 ? "members.exists" : "common.error")}</FormMessage>
        )}
      </div>
    </SectionCard>
  );
}

function Details({ entry, kind }: { entry: DirectoryEntry; kind: Kind }) {
  const t = useTranslations();
  const me = useMe().data;
  const canVerify = kind === "supplier" && me?.permissions.includes("supplier:verify");
  const canReadCatalogue = kind === "supplier" && me?.permissions.includes("catalog:read");
  const categories = useCategories();
  const products = useQuery({
    queryKey: ["organization-products", entry.id],
    queryFn: () => api<Product[]>(`/organizations/${entry.id}/products`),
    enabled: Boolean(canReadCatalogue),
  });
  const verify = useAction(
    (body: Record<string, string>) => api(`/organizations/${entry.id}/verification`, body),
    [["organizations", kind]],
  );
  const facts = [
    [t("directory.location"), [entry.city, entry.country].filter(Boolean).join(", ")],
    [t("org.address"), entry.address],
    [t("org.phone"), entry.phone],
    [t("org.registrationNumber"), entry.registration_number],
    [t("org.taxNumber"), entry.tax_number],
  ];

  return (
    <SectionCard title={entry.name}>
      <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="font-medium">{value || t("directory.notProvided")}</dd>
          </div>
        ))}
      </dl>

      {canVerify && (
        <form
          className="mt-6 space-y-4 border-t border-border pt-5"
          onSubmit={(event) => {
            event.preventDefault();
            verify.run(formValues(event.currentTarget));
          }}
        >
          <h3 className="font-bold">{t("directory.verification")}</h3>
          <SelectField name="status" label={t("directory.status")} defaultValue={entry.verification_status} className="sm:max-w-xs">
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {t(`verification.${status}`)}
              </option>
            ))}
          </SelectField>
          <TextareaField name="note" label={t("directory.note")} defaultValue={entry.verification_note ?? ""} maxLength={1000} />
          {verify.done && <FormMessage tone="success">{t("common.saved")}</FormMessage>}
          {verify.errorStatus !== undefined && <FormMessage tone="error">{t("common.error")}</FormMessage>}
          <Button type="submit" disabled={verify.pending}>
            {t("directory.apply")}
          </Button>
        </form>
      )}

      {me?.permissions.includes("document:read") && (
        <OrganizationDocuments organizationId={entry.id} canReview={me.permissions.includes("document:review")} />
      )}

      {canReadCatalogue && products.data && (
        <div className="mt-6 border-t border-border pt-5">
          <h3 className="mb-3 font-bold">{t("directory.catalogue")}</h3>
          {products.data.length === 0 ? (
            <p className="text-muted-foreground">{t("directory.noProducts")}</p>
          ) : (
            <ProductTable products={products.data} categories={categories.data ?? []} />
          )}
        </div>
      )}
    </SectionCard>
  );
}

/** Pages internes « Acheteurs » et « Fournisseurs ». */
export function DirectoryScreen({ kind }: { kind: Kind }) {
  const t = useTranslations();
  const me = useMe().data;
  const [selectedId, setSelectedId] = useState<string>();
  const organizations = useQuery({
    queryKey: ["organizations", kind],
    queryFn: () => api<DirectoryEntry[]>(`/organizations?kind=${kind}`),
  });
  const selected = organizations.data?.find((entry) => entry.id === selectedId);

  return (
    <div className="space-y-5">
      <PageHeading title={t(`directory.${kind}`)} description={t("spaces.internal.subtitle")} />
      {organizations.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}
      {me?.permissions.includes(`organization:create:${kind}`) && <CreateForm kind={kind} />}

      {organizations.data && (
        <SectionCard title={t(`directory.${kind}`)}>
          {organizations.data.length === 0 ? (
            <p className="text-muted-foreground">{t("directory.empty")}</p>
          ) : (
            <DataTable
              columns={[t("directory.organization"), t("directory.location"), ...(kind === "supplier" ? [t("directory.status")] : []), ""]}
              rows={organizations.data.map((entry) => ({
                key: entry.id,
                cells: [
                  <span key="name" className="font-semibold">{entry.name}</span>,
                  [entry.city, entry.country].filter(Boolean).join(", ") || t("directory.notProvided"),
                  ...(kind === "supplier"
                    ? [
                        <Badge key="status" tone={VERIFICATION_TONE[entry.verification_status]}>
                          {t(`verification.${entry.verification_status}`)}
                        </Badge>,
                      ]
                    : []),
                  <Button
                    key="open"
                    variant="ghost"
                    size="sm"
                    aria-expanded={entry.id === selectedId}
                    onClick={() => setSelectedId(entry.id === selectedId ? undefined : entry.id)}
                  >
                    {t("directory.open")}
                  </Button>,
                ],
              }))}
            />
          )}
        </SectionCard>
      )}

      {selected && (
        <DetailReveal key={selected.id}>
          <Details key={selected.id} entry={selected} kind={kind} />
        </DetailReveal>
      )}
    </div>
  );
}
