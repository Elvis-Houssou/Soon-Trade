"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage, SelectField, TextareaField } from "@/components/ui/field";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";

export type Category = { id: string; name: string; is_active: boolean };
export type Product = {
  id: string;
  name: string;
  category_id: string;
  description: string | null;
  unit: string;
  packaging: string | null;
  min_order_quantity: string;
  available_quantity: string;
  availability: "available" | "limited" | "unavailable";
};

const UNITS = ["kg", "tonne", "litre", "sac", "carton", "unite"];
const AVAILABILITIES = ["available", "limited", "unavailable"] as const;
export const AVAILABILITY_TONE: Record<Product["availability"], Tone> = {
  available: "success",
  limited: "warning",
  unavailable: "neutral",
};

export function useCategories() {
  return useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/categories") });
}

/** Tableau de produits, partagé entre le fournisseur et la vue interne en lecture seule. */
export function ProductTable({
  products,
  categories,
  onEdit,
}: {
  products: Product[];
  categories: Category[];
  onEdit?: (product: Product) => void;
}) {
  const t = useTranslations();
  const format = useFormatter();
  const categoryName = (id: string) => categories.find((category) => category.id === id)?.name ?? "";

  return (
    <DataTable
      columns={[t("catalog.product"), t("catalog.category"), t("catalog.stock"), t("catalog.availability"), ...(onEdit ? [""] : [])]}
      rows={products.map((product) => ({
        key: product.id,
        cells: [
          <span key="name">
            <span className="font-semibold">{product.name}</span>
            {product.packaging && <span className="block text-muted-foreground">{product.packaging}</span>}
          </span>,
          categoryName(product.category_id),
          <span key="stock" className="tabular whitespace-nowrap">
            {format.number(Number(product.available_quantity))} {t(`units.${product.unit}`).toLowerCase()}
          </span>,
          <Badge key="availability" tone={AVAILABILITY_TONE[product.availability]}>
            {t(`availability.${product.availability}`)}
          </Badge>,
          ...(onEdit
            ? [
                <Button key="edit" variant="ghost" size="sm" onClick={() => onEdit(product)}>
                  {t("common.edit")}
                </Button>,
              ]
            : []),
        ],
      }))}
    />
  );
}

function ProductForm({
  product,
  categories,
  onClose,
}: {
  product: Product | null;
  categories: Category[];
  onClose: () => void;
}) {
  const t = useTranslations();
  const save = useAction(
    (body: Record<string, string | null>) =>
      product ? api(`/products/${product.id}`, body, "PATCH") : api("/products", body),
    [["products"]],
  );
  const archive = useAction(() => api(`/products/${product?.id}`, undefined, "DELETE"), [["products"]]);
  const busy = save.pending || archive.pending;
  // Une catégorie désactivée reste proposée pour le produit qui l'utilise déjà.
  const choices = categories.filter((category) => category.is_active || category.id === product?.category_id);

  return (
    <SectionCard title={t(product ? "catalog.editProduct" : "catalog.addProduct")}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          const values = Object.entries(formValues(event.currentTarget));
          save.run(Object.fromEntries(values.map(([key, value]) => [key, value || null])), { onSuccess: onClose });
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field name="name" label={t("catalog.name")} defaultValue={product?.name} minLength={2} maxLength={200} required />
          <SelectField name="category_id" label={t("catalog.category")} defaultValue={product?.category_id} required>
            {choices.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </SelectField>
          <SelectField name="unit" label={t("catalog.unit")} defaultValue={product?.unit ?? "tonne"}>
            {UNITS.map((unit) => (
              <option key={unit} value={unit}>
                {t(`units.${unit}`)}
              </option>
            ))}
          </SelectField>
          <Field name="packaging" label={t("catalog.packaging")} defaultValue={product?.packaging ?? ""} maxLength={200} />
          <Field
            name="min_order_quantity"
            label={t("catalog.minOrder")}
            type="number"
            min={0}
            step="0.001"
            defaultValue={Number(product?.min_order_quantity ?? 0)}
            required
          />
          <Field
            name="available_quantity"
            label={t("catalog.available")}
            type="number"
            min={0}
            step="0.001"
            defaultValue={Number(product?.available_quantity ?? 0)}
            required
          />
          <SelectField name="availability" label={t("catalog.availability")} defaultValue={product?.availability ?? "available"}>
            {AVAILABILITIES.map((availability) => (
              <option key={availability} value={availability}>
                {t(`availability.${availability}`)}
              </option>
            ))}
          </SelectField>
        </div>
        <TextareaField name="description" label={t("catalog.description")} defaultValue={product?.description ?? ""} maxLength={2000} />
        {(save.errorStatus ?? archive.errorStatus) !== undefined && <FormMessage tone="error">{t("common.error")}</FormMessage>}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={busy}>
            {t("common.save")}
          </Button>
          <Button variant="outline" disabled={busy} onClick={onClose}>
            {t("common.cancel")}
          </Button>
          {product && (
            <Button variant="ghost" className="ml-auto" disabled={busy} onClick={() => archive.run(undefined, { onSuccess: onClose })}>
              {t("catalog.archive")}
            </Button>
          )}
        </div>
      </form>
    </SectionCard>
  );
}

/** Page « Catalogue » du fournisseur. */
export function CatalogScreen() {
  const t = useTranslations();
  const products = useQuery({ queryKey: ["products"], queryFn: () => api<Product[]>("/products") });
  const categories = useCategories();
  // undefined = formulaire fermé ; null = nouveau produit ; sinon produit en cours de modification.
  const [editing, setEditing] = useState<Product | null>();
  const hasCategories = categories.data?.some((category) => category.is_active);

  return (
    <div className="space-y-5">
      <PageHeading title={t("catalog.title")} description={t("nav.stock")} />
      {products.error && <FormMessage tone="error">{t("common.forbidden")}</FormMessage>}

      {editing !== undefined && (
        <ProductForm
          key={editing?.id ?? "new"}
          product={editing}
          categories={categories.data ?? []}
          onClose={() => setEditing(undefined)}
        />
      )}

      {products.data && (
        <SectionCard
          title={t("nav.catalog")}
          action={
            hasCategories && editing === undefined ? (
              <Button size="sm" className="shadow-none" onClick={() => setEditing(null)}>
                {t("catalog.addProduct")}
              </Button>
            ) : undefined
          }
        >
          {categories.data && !hasCategories ? (
            <p className="text-muted-foreground">{t("catalog.noCategories")}</p>
          ) : products.data.length === 0 ? (
            <p className="text-muted-foreground">{t("catalog.empty")}</p>
          ) : (
            <ProductTable products={products.data} categories={categories.data ?? []} onEdit={setEditing} />
          )}
        </SectionCard>
      )}
    </div>
  );
}

/** Page interne « Paramètres » : gestion des catégories de produits. */
export function CategoriesScreen() {
  const t = useTranslations();
  const categories = useCategories();
  const create = useAction((body: Record<string, string>) => api("/categories", body), [["categories"]]);
  const toggle = useAction(
    (category: Category) => api(`/categories/${category.id}`, { is_active: !category.is_active }, "PATCH"),
    [["categories"]],
  );

  return (
    <div className="space-y-5">
      <PageHeading title={t("categories.title")} description={t("categories.intro")} />
      <SectionCard title={t("nav.settings")}>
        <form
          className="grid items-end gap-4 sm:grid-cols-[1fr_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            create.run(formValues(form), { onSuccess: () => form.reset() });
          }}
        >
          <Field name="name" label={t("categories.name")} minLength={2} maxLength={120} required />
          <Button type="submit" size="lg" className="h-11" disabled={create.pending}>
            {t("common.add")}
          </Button>
        </form>
        {create.errorStatus !== undefined && (
          <div className="mt-3">
            <FormMessage tone="error">
              {t(create.errorStatus === 409 ? "categories.exists" : create.errorStatus === 403 ? "common.forbidden" : "common.error")}
            </FormMessage>
          </div>
        )}

        {categories.data?.length === 0 ? (
          <p className="mt-6 text-muted-foreground">{t("categories.empty")}</p>
        ) : (
          <ul className="mt-6 divide-y divide-border">
            {categories.data?.map((category) => (
              <li key={category.id} className="flex items-center justify-between gap-3 py-2.5">
                <span className="font-semibold">{category.name}</span>
                <span className="flex items-center gap-3">
                  <Badge tone={category.is_active ? "success" : "neutral"}>
                    {t(category.is_active ? "categories.enabled" : "categories.disabled")}
                  </Badge>
                  <Button variant="ghost" size="sm" disabled={toggle.pending} onClick={() => toggle.run(category)}>
                    {t(category.is_active ? "categories.disable" : "categories.enable")}
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}
