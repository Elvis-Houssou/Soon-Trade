"use client";

import { useFormatter, useTranslations } from "next-intl";
import { Badge, type Tone } from "@/components/ui/badge";
import { useCategories } from "@/features/catalog/catalog-screens";

export type RequestStatus =
  | "draft"
  | "submitted"
  | "info_requested"
  | "qualified"
  | "in_sourcing"
  | "proposal_sent"
  | "accepted"
  | "closed"
  | "rejected"
  | "cancelled";

export type RequestEvent = {
  created_at: string;
  from_status: RequestStatus | null;
  to_status: RequestStatus;
  message: string | null;
  /** Présent uniquement dans les réponses de l'espace interne. */
  actor_name?: string;
};

export type PurchaseRequest = {
  id: string;
  reference: string;
  status: RequestStatus;
  created_at: string;
  product_name: string;
  category_id: string | null;
  quantity: string;
  unit: string;
  specifications: string | null;
  packaging: string | null;
  delivery_location: string;
  desired_date: string | null;
  additional_info: string | null;
  history: RequestEvent[];
  /** Présent uniquement dans les réponses de l'espace interne. */
  buyer_name?: string;
};

const STATUS_TONE: Record<RequestStatus, Tone> = {
  draft: "neutral",
  submitted: "primary",
  info_requested: "warning",
  qualified: "success",
  in_sourcing: "primary",
  proposal_sent: "warning",
  accepted: "success",
  closed: "neutral",
  rejected: "danger",
  cancelled: "neutral",
};

export function StatusBadge({ status }: { status: RequestStatus }) {
  const t = useTranslations("requestStatus");
  return <Badge tone={STATUS_TONE[status]}>{t(status)}</Badge>;
}

export function useQuantity() {
  const t = useTranslations("units");
  const format = useFormatter();
  return (request: Pick<PurchaseRequest, "quantity" | "unit">) =>
    `${format.number(Number(request.quantity))} ${t(request.unit).toLowerCase()}`;
}

export function RequestFacts({ request }: { request: PurchaseRequest }) {
  const t = useTranslations();
  const format = useFormatter();
  const quantity = useQuantity();
  const categories = useCategories();
  const facts = [
    [t("requests.product"), request.product_name],
    [t("requests.category"), categories.data?.find((category) => category.id === request.category_id)?.name],
    [t("requests.quantity"), quantity(request)],
    [t("requests.packaging"), request.packaging],
    [t("requests.deliveryLocation"), request.delivery_location],
    [t("requests.desiredDate"), request.desired_date && format.dateTime(new Date(request.desired_date), { dateStyle: "long" })],
    [t("requests.specifications"), request.specifications],
    [t("requests.additionalInfo"), request.additional_info],
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

export function RequestHistory({ history }: { history: RequestEvent[] }) {
  const t = useTranslations();
  const format = useFormatter();
  return (
    <div className="mt-6 border-t border-border pt-5">
      <h3 className="mb-3 font-bold">{t("requests.history")}</h3>
      <ol className="space-y-3">
        {history.map((event, index) => (
          <li key={index} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <StatusBadge status={event.to_status} />
            <span className="text-sm text-muted-foreground">
              {format.dateTime(new Date(event.created_at), { dateStyle: "medium", timeStyle: "short" })}
              {event.actor_name && ` · ${event.actor_name}`}
            </span>
            {event.message && <p className="basis-full whitespace-pre-line">{event.message}</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}
