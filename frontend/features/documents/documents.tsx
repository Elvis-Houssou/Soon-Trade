"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { DataTable } from "@/components/dashboard/widgets";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage, SelectField } from "@/components/ui/field";
import { api } from "@/lib/api";
import { useAction } from "@/lib/use-action";

type DocumentRow = {
  id: string;
  created_at: string;
  doc_type: string;
  filename: string;
  size_bytes: number;
  status: "pending" | "approved" | "rejected";
};

const TYPES = ["company_registration", "tax_certificate", "id_document", "offer_attachment", "other"];
const STATUS_TONE: Record<DocumentRow["status"], Tone> = { pending: "warning", approved: "success", rejected: "danger" };

/** Demande un lien temporaire à l'API puis l'ouvre : aucun lien permanent n'existe. */
export async function openDocument(id: string) {
  const { url } = await api<{ url: string }>(`/documents/${id}/url`);
  window.open(url, "_blank", "noopener");
}

function DocumentTable({ documents, onReview }: { documents: DocumentRow[]; onReview?: (id: string, status: string) => void }) {
  const t = useTranslations("documents");
  const format = useFormatter();
  return (
    <DataTable
      columns={[t("document"), t("addedOn"), t("status"), ""]}
      rows={documents.map((document) => ({
        key: document.id,
        cells: [
          <span key="name">
            <span className="font-semibold">{t(document.doc_type)}</span>
            <span className="block break-all text-muted-foreground">{document.filename}</span>
          </span>,
          format.dateTime(new Date(document.created_at), { dateStyle: "medium" }),
          <Badge key="status" tone={STATUS_TONE[document.status]}>{t(document.status)}</Badge>,
          <span key="actions" className="flex flex-wrap gap-1">
            <Button variant="ghost" size="sm" onClick={() => openDocument(document.id)}>
              {t("open")}
            </Button>
            {onReview && document.status !== "approved" && (
              <Button variant="ghost" size="sm" onClick={() => onReview(document.id, "approved")}>
                {t("approve")}
              </Button>
            )}
            {onReview && document.status !== "rejected" && (
              <Button variant="ghost" size="sm" onClick={() => onReview(document.id, "rejected")}>
                {t("reject")}
              </Button>
            )}
          </span>,
        ],
      }))}
    />
  );
}

/** Documents de sa propre organisation, avec dépôt si le rôle le permet. */
export function DocumentsCard({ canUpload }: { canUpload: boolean }) {
  const t = useTranslations("documents");
  const documents = useQuery({ queryKey: ["documents"], queryFn: () => api<DocumentRow[]>("/documents") });
  const upload = useAction((form: FormData) => api("/documents", form), [["documents"]]);

  return (
    <SectionCard title={t("title")}>
      <p className="mb-4 text-muted-foreground">{t("intro")}</p>
      {documents.data?.length === 0 ? (
        <p className="text-muted-foreground">{t("empty")}</p>
      ) : (
        <DocumentTable documents={documents.data ?? []} />
      )}

      {canUpload && (
        <form
          className="mt-6 grid items-start gap-4 border-t border-border pt-5 md:grid-cols-[14rem_1fr_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            upload.run(new FormData(form), { onSuccess: () => form.reset() });
          }}
        >
          <SelectField name="doc_type" label={t("type")}>
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {t(type)}
              </option>
            ))}
          </SelectField>
          <Field
            name="file"
            type="file"
            label={t("file")}
            hint={t("hint")}
            accept="application/pdf,image/jpeg,image/png"
            className="py-2"
            required
          />
          <Button type="submit" size="lg" className="h-11 md:mt-[1.875rem]" disabled={upload.pending}>
            {t("upload")}
          </Button>
        </form>
      )}
      {upload.errorStatus !== undefined && (
        <div className="mt-3">
          <FormMessage tone="error">{t("invalid")}</FormMessage>
        </div>
      )}
    </SectionCard>
  );
}

/** Vue interne des documents d'une organisation cliente, avec validation si le rôle le permet. */
export function OrganizationDocuments({ organizationId, canReview }: { organizationId: string; canReview: boolean }) {
  const t = useTranslations("documents");
  const key = ["organization-documents", organizationId];
  const documents = useQuery({
    queryKey: key,
    queryFn: () => api<DocumentRow[]>(`/organizations/${organizationId}/documents`),
  });
  const review = useAction(
    ({ id, status }: { id: string; status: string }) => api(`/documents/${id}/review`, { status }),
    [key],
  );
  if (!documents.data) return null;

  return (
    <div className="mt-6 border-t border-border pt-5">
      <h3 className="mb-3 font-bold">{t("title")}</h3>
      {documents.data.length === 0 ? (
        <p className="text-muted-foreground">{t("empty")}</p>
      ) : (
        <DocumentTable
          documents={documents.data}
          onReview={canReview ? (id, status) => review.run({ id, status }) : undefined}
        />
      )}
    </div>
  );
}
