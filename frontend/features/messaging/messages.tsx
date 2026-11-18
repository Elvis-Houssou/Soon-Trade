"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { useMe } from "@/components/auth/session";
import { PageHeading } from "@/components/dashboard/widgets";
import { DetailReveal } from "@/components/motion/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage, SelectField, TextareaField } from "@/components/ui/field";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";
import { cn } from "@/lib/utils";

type Message = { id: string; created_at: string; from_staff: boolean; author_name: string | null; body: string; internal?: boolean };

type Summary = {
  id: string;
  reference: string;
  subject: string;
  context_reference: string | null;
  status: "open" | "closed";
  last_message_at: string;
  last_message: string | null;
  unread: boolean;
  /** Présents uniquement côté interne. */
  organization_id?: string;
  organization_name?: string;
  organization_kind?: string;
};

type Conversation = Summary & { messages: Message[] };

function ConversationList({ items, selectedId, onSelect, internal = false }: { items: Summary[]; selectedId?: string; onSelect: (id: string) => void; internal?: boolean }) {
  const t = useTranslations("messages");
  const format = useFormatter();
  if (items.length === 0) return <p className="text-muted-foreground">{t("empty")}</p>;
  return (
    <ul className="-mx-2 space-y-1">
      {items.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            aria-current={item.id === selectedId ? "true" : undefined}
            onClick={() => onSelect(item.id)}
            className={cn(
              "w-full rounded-control px-3 py-2.5 text-left transition-colors hover:bg-surface-muted",
              item.id === selectedId && "bg-primary-soft hover:bg-primary-soft",
            )}
          >
            <span className="flex items-center gap-2">
              {item.unread && <span aria-label={t("unread")} className="size-2 shrink-0 rounded-full bg-primary" />}
              <span className={cn("min-w-0 flex-1 truncate", item.unread ? "font-bold" : "font-semibold")}>{item.subject}</span>
              <span className="shrink-0 text-xs text-muted-foreground">{format.relativeTime(new Date(item.last_message_at))}</span>
            </span>
            <span className="mt-0.5 block truncate text-sm text-muted-foreground">
              {internal && `${item.organization_name} · `}
              {item.last_message}
            </span>
            {item.status === "closed" && <Badge className="mt-1">{t("closed")}</Badge>}
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Fil de messages ; `mine` dit si un message vient du côté de celui qui lit. */
function Thread({ conversation, mine }: { conversation: Conversation; mine: (message: Message) => boolean }) {
  const t = useTranslations("messages");
  const format = useFormatter();
  return (
    <ol className="space-y-3">
      {conversation.messages.map((message) => {
        const own = mine(message);
        return (
          <li key={message.id} className={cn("flex", own ? "justify-end" : "justify-start")}>
            <div
              className={cn(
                "max-w-[85%] rounded-card px-4 py-2.5",
                message.internal
                  ? "border border-dashed border-warning-foreground/40 bg-warning-soft text-warning-foreground"
                  : own
                    ? "bg-primary text-primary-foreground"
                    : "bg-surface-muted",
              )}
            >
              <p className={cn("mb-1 text-xs", own && !message.internal ? "text-primary-foreground/80" : "text-muted-foreground")}>
                {message.internal && `${t("internalNote")} · `}
                {message.from_staff ? (message.author_name ?? "SOON TRADE") : (message.author_name ?? "")}
                {" · "}
                {format.dateTime(new Date(message.created_at), { dateStyle: "medium", timeStyle: "short" })}
              </p>
              <p className="whitespace-pre-line">{message.body}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function ReplyForm({ path, refresh, internal = false }: { path: string; refresh: string[][]; internal?: boolean }) {
  const t = useTranslations("messages");
  const tc = useTranslations("common");
  const send = useAction((body: { body: string; internal?: boolean }) => api(path, body), refresh);
  return (
    <form
      className="mt-5 space-y-3 border-t border-border pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const data = new FormData(form);
        send.run({ body: String(data.get("body") ?? "").trim(), ...(internal ? { internal: data.get("internal") === "on" } : {}) }, { onSuccess: () => form.reset() });
      }}
    >
      <TextareaField name="body" label={t("reply")} maxLength={4000} required />
      <div className="flex flex-wrap items-center gap-4">
        <Button type="submit" disabled={send.pending}>
          {t("send")}
        </Button>
        {internal && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="internal" className="size-4 accent-primary" />
            {t("asInternalNote")}
          </label>
        )}
      </div>
      {send.errorStatus !== undefined && <FormMessage tone="error">{tc("error")}</FormMessage>}
    </form>
  );
}

function NewConversation({ path, refresh, clients, onCreated }: { path: string; refresh: string[][]; clients?: { id: string; name: string; kind: string }[]; onCreated: (id: string) => void }) {
  const t = useTranslations("messages");
  const tc = useTranslations("common");
  const preset = useSearchParams().get("new") ?? "";
  const start = useAction((body: Record<string, string | null>) => api<Conversation>(path, body), refresh);
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const values = formValues(event.currentTarget);
        start.run({ ...values, context_reference: values.context_reference || null }, { onSuccess: (created) => onCreated((created as Conversation).id) });
      }}
    >
      {clients && (
        <SelectField name="organization_id" label={t("client")} defaultValue={preset} required>
          <option value="" disabled>
            —
          </option>
          {clients.map((client) => (
            <option key={client.id} value={client.id}>
              {client.name} · {t(`kinds.${client.kind}`)}
            </option>
          ))}
        </SelectField>
      )}
      <Field name="subject" label={t("subject")} minLength={2} maxLength={200} required />
      <Field name="context_reference" label={t("context")} hint={t("contextHint")} maxLength={40} />
      <TextareaField name="body" label={t("message")} maxLength={4000} required />
      {start.errorStatus !== undefined && <FormMessage tone="error">{tc("error")}</FormMessage>}
      <Button type="submit" disabled={start.pending}>
        {t("send")}
      </Button>
    </form>
  );
}

function Layout({ title, intro, list, detail }: { title: string; intro: string; list: React.ReactNode; detail: React.ReactNode }) {
  return (
    <div className="space-y-5">
      <PageHeading title={title} description={intro} />
      <div className="grid items-start gap-5 lg:grid-cols-[22rem_1fr]">
        {list}
        {detail}
      </div>
    </div>
  );
}

/** Page « Messages » de l'acheteur et du fournisseur : on n'écrit qu'à SOON TRADE. */
export function ClientMessagesScreen() {
  const t = useTranslations("messages");
  const [selectedId, setSelectedId] = useState<string | undefined>(useSearchParams().get("id") ?? undefined);
  const [writing, setWriting] = useState(false);
  const list = useQuery({ queryKey: ["conversations"], queryFn: () => api<Summary[]>("/conversations") });
  const detail = useQuery({
    queryKey: ["conversation", selectedId],
    queryFn: () => api<Conversation>(`/conversations/${selectedId}`),
    enabled: Boolean(selectedId),
  });
  const refresh = [["conversations"], ["conversation", selectedId ?? ""]];

  return (
    <Layout
      title={t("title")}
      intro={t("clientIntro")}
      list={
        <SectionCard
          title={t("conversations")}
          action={
            <Button size="sm" className="shadow-none" onClick={() => { setWriting(true); setSelectedId(undefined); }}>
              {t("new")}
            </Button>
          }
        >
          {list.error ? <FormMessage tone="error">{t("forbidden")}</FormMessage> : list.data && <ConversationList items={list.data} selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setWriting(false); }} />}
        </SectionCard>
      }
      detail={
        writing ? (
          <DetailReveal key="new">
            <SectionCard title={t("new")}>
              <p className="mb-4 text-sm text-muted-foreground">{t("newHint")}</p>
              <NewConversation path="/conversations" refresh={[["conversations"]]} onCreated={(id) => { setWriting(false); setSelectedId(id); }} />
            </SectionCard>
          </DetailReveal>
        ) : detail.data ? (
          <DetailReveal key={detail.data.id}>
            <SectionCard title={detail.data.subject} action={<span className="text-sm text-muted-foreground">{detail.data.reference}</span>}>
              {detail.data.context_reference && <p className="mb-4 text-sm text-muted-foreground">{t("about", { reference: detail.data.context_reference })}</p>}
              <Thread conversation={detail.data} mine={(message) => !message.from_staff} />
              <ReplyForm path={`/conversations/${detail.data.id}/messages`} refresh={refresh} />
            </SectionCard>
          </DetailReveal>
        ) : (
          <p className="hidden rounded-card border border-dashed border-border p-8 text-center text-muted-foreground lg:block">{t("pick")}</p>
        )
      }
    />
  );
}

/** Page interne « Messages » : tous les fils, notes internes, ouverture d'un fil avec un client. */
export function InternalMessagesScreen() {
  const t = useTranslations("messages");
  const me = useMe().data;
  const params = useSearchParams();
  const [selectedId, setSelectedId] = useState<string | undefined>(params.get("id") ?? undefined);
  const [writing, setWriting] = useState(Boolean(params.get("new")));
  const canReply = Boolean(me?.permissions.includes("conversation:reply"));
  const list = useQuery({ queryKey: ["internal-conversations"], queryFn: () => api<Summary[]>("/internal/conversations") });
  const clients = useQuery({
    queryKey: ["crm-clients"],
    queryFn: () => api<{ id: string; name: string; kind: string }[]>("/internal/crm"),
    enabled: writing,
  });
  const detail = useQuery({
    queryKey: ["internal-conversation", selectedId],
    queryFn: () => api<Conversation>(`/internal/conversations/${selectedId}`),
    enabled: Boolean(selectedId),
  });
  const refresh = [["internal-conversations"], ["internal-conversation", selectedId ?? ""]];
  const toggle = useAction((action: string) => api(`/internal/conversations/${selectedId}/${action}`, {}), refresh);

  return (
    <Layout
      title={t("title")}
      intro={t("internalIntro")}
      list={
        <SectionCard
          title={t("conversations")}
          action={
            canReply ? (
              <Button size="sm" className="shadow-none" onClick={() => { setWriting(true); setSelectedId(undefined); }}>
                {t("new")}
              </Button>
            ) : undefined
          }
        >
          {list.error ? <FormMessage tone="error">{t("forbidden")}</FormMessage> : list.data && <ConversationList items={list.data} selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setWriting(false); }} internal />}
        </SectionCard>
      }
      detail={
        writing && canReply ? (
          <DetailReveal key="new">
            <SectionCard title={t("new")}>
              <p className="mb-4 text-sm text-muted-foreground">{t("newInternalHint")}</p>
              {clients.data && (
                <NewConversation path="/internal/conversations" refresh={[["internal-conversations"]]} clients={clients.data} onCreated={(id) => { setWriting(false); setSelectedId(id); }} />
              )}
            </SectionCard>
          </DetailReveal>
        ) : detail.data ? (
          <DetailReveal key={detail.data.id}>
            <SectionCard
              title={`${detail.data.subject} · ${detail.data.organization_name}`}
              action={
                canReply ? (
                  <Button variant="ghost" size="sm" disabled={toggle.pending} onClick={() => toggle.run(detail.data!.status === "open" ? "close" : "reopen")}>
                    {t(detail.data.status === "open" ? "close" : "reopen")}
                  </Button>
                ) : undefined
              }
            >
              <p className="mb-4 text-sm text-muted-foreground">
                {detail.data.reference} · {t(`kinds.${detail.data.organization_kind}`)}
                {detail.data.context_reference && ` · ${t("about", { reference: detail.data.context_reference })}`}
              </p>
              <Thread conversation={detail.data} mine={(message) => message.from_staff} />
              {canReply && <ReplyForm path={`/internal/conversations/${detail.data.id}/messages`} refresh={refresh} internal />}
            </SectionCard>
          </DetailReveal>
        ) : (
          <p className="hidden rounded-card border border-dashed border-border p-8 text-center text-muted-foreground lg:block">{t("pick")}</p>
        )
      }
    />
  );
}
