"use client";

import { useFormatter, useTranslations } from "next-intl";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { openDocument } from "@/features/documents/documents";
import { useQuantity } from "@/features/requests/shared";

export type SolicitationStatus = "draft" | "sent" | "viewed" | "answered" | "declined" | "expired" | "cancelled";
export type OfferStatus = "submitted" | "withdrawn" | "under_review" | "retained" | "not_retained" | "expired";

export type OfferVersion = {
  version: number;
  created_at: string;
  unit_price: string;
  currency: string;
  quantity: string;
  total: string;
  lead_time_days: number;
  valid_until: string;
  packaging: string | null;
  conditions: string | null;
  attachments: { id: string; filename: string }[];
};

export type Offer = { id: string; reference: string; status: OfferStatus; versions: OfferVersion[] };

export type Solicitation = {
  id: string;
  reference: string;
  status: SolicitationStatus;
  sent_at: string | null;
  product_name: string;
  quantity: string;
  unit: string;
  specifications: string | null;
  packaging: string | null;
  delivery_location: string;
  desired_date: string | null;
  response_deadline: string;
  message: string | null;
  decline_reason: string | null;
  offer: Offer | null;
};

/** Champs ajoutés par les réponses de l'espace interne. */
export type InternalSolicitation = Solicitation & {
  created_at: string;
  organization_id: string;
  supplier_name: string;
  case_id: string;
  case_reference: string;
  created_by: { id: string; full_name: string };
  viewed_at: string | null;
};

const SOLICITATION_TONE: Record<SolicitationStatus, Tone> = {
  draft: "neutral",
  sent: "primary",
  viewed: "primary",
  answered: "success",
  declined: "danger",
  expired: "neutral",
  cancelled: "neutral",
};
const OFFER_TONE: Record<OfferStatus, Tone> = {
  submitted: "primary",
  withdrawn: "neutral",
  under_review: "warning",
  retained: "success",
  not_retained: "danger",
  expired: "neutral",
};

export function SolicitationBadge({ status }: { status: SolicitationStatus }) {
  const t = useTranslations("solicitationStatus");
  return <Badge tone={SOLICITATION_TONE[status]}>{t(status)}</Badge>;
}

export function OfferBadge({ status }: { status: OfferStatus }) {
  const t = useTranslations("offerStatus");
  return <Badge tone={OFFER_TONE[status]}>{t(status)}</Badge>;
}

export function useMoney() {
  const format = useFormatter();
  return (amount: string, currency: string) =>
    format.number(Number(amount), { style: "currency", currency, maximumFractionDigits: 2 });
}

export function useDay() {
  const format = useFormatter();
  return (day: string) => format.dateTime(new Date(day), { dateStyle: "medium" });
}

/** Le besoin tel que SOON TRADE l'a rédigé pour le fournisseur. */
export function NeedFacts({ solicitation }: { solicitation: Solicitation }) {
  const t = useTranslations();
  const quantity = useQuantity();
  const day = useDay();
  const facts = [
    [t("requests.product"), solicitation.product_name],
    [t("requests.quantity"), quantity(solicitation)],
    [t("requests.packaging"), solicitation.packaging],
    [t("requests.deliveryLocation"), solicitation.delivery_location],
    [t("requests.desiredDate"), solicitation.desired_date && day(solicitation.desired_date)],
    [t("solicitations.deadline"), day(solicitation.response_deadline)],
    [t("requests.specifications"), solicitation.specifications],
    [t("solicitations.message"), solicitation.message],
  ];
  return (
    <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
      {facts.map(([label, value]) => (
        <div key={label}>
          <dt className="text-sm text-muted-foreground">{label}</dt>
          <dd className="font-medium whitespace-pre-line">{value || t("directory.notProvided")}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Attachments({ attachments }: { attachments: OfferVersion["attachments"] }) {
  return (
    <span className="flex flex-wrap gap-1">
      {attachments.map((attachment) => (
        <Button key={attachment.id} variant="ghost" size="sm" className="max-w-56 truncate" onClick={() => openDocument(attachment.id)}>
          {attachment.filename}
        </Button>
      ))}
    </span>
  );
}

/** Contenu d'une version d'offre ; les versions précédentes restent consultables. */
export function OfferFacts({ offer, unit }: { offer: Offer; unit: string }) {
  const t = useTranslations();
  const money = useMoney();
  const quantity = useQuantity();
  const day = useDay();
  const current = offer.versions.at(-1);
  if (!current) return null;
  const facts = [
    [t("offers.unitPrice"), money(current.unit_price, current.currency)],
    [t("offers.quantity"), quantity({ quantity: current.quantity, unit })],
    [t("offers.total"), money(current.total, current.currency)],
    [t("offers.leadTime"), t("offers.days", { count: current.lead_time_days })],
    [t("offers.validUntil"), day(current.valid_until)],
    [t("requests.packaging"), current.packaging],
    [t("offers.conditions"), current.conditions],
  ];
  return (
    <div className="space-y-4">
      <p className="flex flex-wrap items-center gap-3">
        <span className="font-semibold">{offer.reference}</span>
        <OfferBadge status={offer.status} />
        <span className="text-sm text-muted-foreground">{t("offers.version", { version: current.version })}</span>
      </p>
      <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="font-medium whitespace-pre-line">{value || t("directory.notProvided")}</dd>
          </div>
        ))}
      </dl>
      {current.attachments.length > 0 && <Attachments attachments={current.attachments} />}
      {offer.versions.length > 1 && (
        <details>
          <summary className="cursor-pointer text-sm font-semibold">{t("offers.previousVersions")}</summary>
          <ul className="mt-2 space-y-1 text-sm">
            {offer.versions.slice(0, -1).map((version) => (
              <li key={version.version}>
                {t("offers.version", { version: version.version })} · {day(version.created_at)} ·{" "}
                {money(version.unit_price, version.currency)} · {t("offers.days", { count: version.lead_time_days })}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
