"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Notification = {
  id: string;
  created_at: string;
  kind: string;
  params: Record<string, string>;
  link: string;
  read_at: string | null;
};
type Notifications = { unread: number; items: Notification[] };

// shortcut: relève toutes les 30 s ; passer à des évènements serveur si l'attente gêne.
const POLL_MS = 30_000;

/** Cloche de l'en-tête : notifications de l'utilisateur, lues ou non. */
export function NotificationBell() {
  const t = useTranslations("notifications");
  const format = useFormatter();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<Notifications>("/notifications"),
    refetchInterval: POLL_MS,
  });
  const unread = notifications.data?.unread ?? 0;

  // Fermeture au clic extérieur et à Échap.
  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => root.current?.contains(event.target as Node) || setOpen(false);
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const markRead = async (ids?: string[]) => {
    const data = await api<Notifications>("/notifications/read", ids ? { ids } : {});
    queryClient.setQueryData(["notifications"], data);
  };

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-label={unread ? t("labelUnread", { count: unread }) : t("label")}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="relative grid size-10 place-items-center rounded-full border border-border bg-surface text-muted-foreground transition-colors hover:text-foreground"
      >
        <Bell className="size-4" aria-hidden />
        {unread > 0 && (
          <span className="tabular absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-primary px-1 text-[0.6875rem] font-bold text-primary-foreground">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-12 z-20 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-card border border-border bg-surface shadow-raised">
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
            <p className="font-semibold">{t("title")}</p>
            {unread > 0 && (
              <button type="button" onClick={() => markRead()} className="text-sm font-semibold text-primary-soft-foreground hover:underline">
                {t("markAll")}
              </button>
            )}
          </div>
          {notifications.data?.items.length ? (
            <ul className="max-h-96 divide-y divide-border overflow-y-auto">
              {notifications.data.items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={async () => {
                      setOpen(false);
                      if (!item.read_at) await markRead([item.id]);
                      router.push(`/${item.link}`);
                    }}
                    className={cn("flex w-full gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-surface-muted", !item.read_at && "bg-primary-soft/40")}
                  >
                    <span aria-hidden className={cn("mt-1.5 size-2 shrink-0 rounded-full", item.read_at ? "bg-transparent" : "bg-primary")} />
                    <span className="min-w-0">
                      <span className={cn("block", !item.read_at && "font-semibold")}>
                        {t.has(`kinds.${item.kind}`) ? t(`kinds.${item.kind}`, item.params) : item.kind}
                      </span>
                      <span className="block text-xs text-muted-foreground">
                        {format.relativeTime(new Date(item.created_at))}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">{t("empty")}</p>
          )}
        </div>
      )}
    </div>
  );
}
