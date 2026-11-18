"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useMe } from "@/components/auth/session";
import { DataTable, PageHeading } from "@/components/dashboard/widgets";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SectionCard } from "@/components/ui/card";
import { Field, FormMessage, SelectField } from "@/components/ui/field";
import { DocumentsCard } from "@/features/documents/documents";
import type { SpaceId } from "@/features/navigation/spaces";
import { api } from "@/lib/api";
import { formValues, useAction } from "@/lib/use-action";

export type Organization = {
  id: string;
  name: string;
  kind: SpaceId;
  country: string | null;
  city: string | null;
  address: string | null;
  phone: string | null;
  registration_number: string | null;
  tax_number: string | null;
  verification_status: "pending" | "verified" | "rejected" | "suspended";
};

type Member = { user_id: string; email: string; full_name: string; role: string; is_active: boolean };
type PendingInvitation = { id: string; email: string; role: string; expires_at: string };

export const VERIFICATION_TONE: Record<Organization["verification_status"], Tone> = {
  pending: "warning",
  verified: "success",
  rejected: "danger",
  suspended: "neutral",
};

// Rôles proposés à l'invitation ; l'API refuse de toute façon un rôle d'un autre espace.
const ROLES: Record<SpaceId, string[]> = {
  buyer: ["buyer_member", "buyer_owner"],
  supplier: ["supplier_member", "supplier_owner"],
  internal: ["sourcing_agent", "sales_agent", "finance_agent", "logistics_agent", "support_agent", "auditor", "admin"],
};

const PROFILE_FIELDS = [
  ["country", "country"],
  ["city", "city"],
  ["address", "address"],
  ["phone", "phone"],
  ["registration_number", "registrationNumber"],
  ["tax_number", "taxNumber"],
] as const;

function ProfileCard({ canEdit }: { canEdit: boolean }) {
  const t = useTranslations();
  const { data: organization } = useQuery({ queryKey: ["organization"], queryFn: () => api<Organization>("/organization") });
  const save = useAction((changes: Record<string, string | null>) => api("/organization", changes, "PATCH"), [["organization"]]);
  if (!organization) return null;

  return (
    <SectionCard
      title={organization.name}
      action={
        organization.kind === "supplier" && (
          <Badge tone={VERIFICATION_TONE[organization.verification_status]}>
            {t(`verification.${organization.verification_status}`)}
          </Badge>
        )
      }
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          const values = formValues(event.currentTarget);
          // Un champ vidé est envoyé comme « non renseigné », pas comme chaîne vide.
          const changes = Object.entries({ ...values, country: values.country.toUpperCase() });
          save.run(Object.fromEntries(changes.map(([key, value]) => [key, value || null])));
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {PROFILE_FIELDS.map(([name, labelKey]) => (
            <Field
              key={name}
              name={name}
              label={t(`org.${labelKey}`)}
              defaultValue={organization[name] ?? ""}
              disabled={!canEdit}
              {...(name === "country" ? { pattern: "[A-Za-z]{2}", maxLength: 2 } : {})}
            />
          ))}
        </div>
        {save.done && <FormMessage tone="success">{t("common.saved")}</FormMessage>}
        {save.errorStatus !== undefined && <FormMessage tone="error">{t("common.error")}</FormMessage>}
        {canEdit ? (
          <Button type="submit" disabled={save.pending}>
            {t("common.save")}
          </Button>
        ) : (
          <p className="text-sm text-muted-foreground">{t("org.readOnly")}</p>
        )}
      </form>
    </SectionCard>
  );
}

export function MembersCard({ kind }: { kind: SpaceId }) {
  const t = useTranslations();
  const format = useFormatter();
  const me = useMe().data;
  const members = useQuery({ queryKey: ["members"], queryFn: () => api<Member[]>("/members") });
  const invitations = useQuery({ queryKey: ["invitations"], queryFn: () => api<PendingInvitation[]>("/invitations") });
  const update = useAction(
    ({ userId, ...changes }: { userId: string; role?: string; is_active?: boolean }) =>
      api(`/members/${userId}`, changes, "PATCH"),
    [["members"]],
  );
  const invite = useAction((body: Record<string, string>) => api("/invitations", body), [["invitations"]]);
  const cancel = useAction((id: string) => api(`/invitations/${id}`, undefined, "DELETE"), [["invitations"]]);

  return (
    <SectionCard title={t("members.title")}>
      <DataTable
        columns={[t("members.name"), t("members.role"), t("members.status"), ""]}
        rows={(members.data ?? []).map((member) => {
          const self = member.user_id === me?.id;
          return {
            key: member.user_id,
            cells: [
              <span key="name">
                <span className="font-semibold">
                  {member.full_name} {self && <span className="font-normal text-muted-foreground">({t("members.you")})</span>}
                </span>
                <span className="block text-muted-foreground">{member.email}</span>
              </span>,
              self ? (
                t(`roles.${member.role}`)
              ) : (
                <select
                  key="role"
                  aria-label={`${t("members.role")} — ${member.full_name}`}
                  value={member.role}
                  disabled={update.pending}
                  onChange={(event) => update.run({ userId: member.user_id, role: event.target.value })}
                  className="h-9 rounded-control border border-border bg-surface px-2"
                >
                  {ROLES[kind].map((role) => (
                    <option key={role} value={role}>
                      {t(`roles.${role}`)}
                    </option>
                  ))}
                </select>
              ),
              <Badge key="status" tone={member.is_active ? "success" : "neutral"}>
                {t(member.is_active ? "members.active" : "members.inactive")}
              </Badge>,
              !self && (
                <Button
                  key="toggle"
                  variant="ghost"
                  size="sm"
                  disabled={update.pending}
                  onClick={() => update.run({ userId: member.user_id, is_active: !member.is_active })}
                >
                  {t(member.is_active ? "members.deactivate" : "members.reactivate")}
                </Button>
              ),
            ],
          };
        })}
      />

      <form
        className="mt-6 grid items-end gap-4 border-t border-border pt-5 sm:grid-cols-[1fr_12rem_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          invite.run(formValues(form), { onSuccess: () => form.reset() });
        }}
      >
        <Field name="email" type="email" label={t("members.invite")} placeholder={t("members.email")} required />
        <SelectField name="role" label={t("members.role")} defaultValue={ROLES[kind][0]}>
          {ROLES[kind].map((role) => (
            <option key={role} value={role}>
              {t(`roles.${role}`)}
            </option>
          ))}
        </SelectField>
        <Button type="submit" size="lg" className="h-11" disabled={invite.pending}>
          {t("members.send")}
        </Button>
      </form>
      <div className="mt-3 space-y-2">
        {invite.done && <FormMessage tone="success">{t("common.saved")}</FormMessage>}
        {invite.errorStatus !== undefined && (
          <FormMessage tone="error">{t(invite.errorStatus === 409 ? "members.exists" : "common.error")}</FormMessage>
        )}
      </div>

      {Boolean(invitations.data?.length) && (
        <div className="mt-6">
          <h3 className="mb-2 font-bold">{t("members.pending")}</h3>
          <ul className="divide-y divide-border">
            {invitations.data?.map((invitation) => (
              <li key={invitation.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
                <span>
                  <span className="font-semibold">{invitation.email}</span>
                  <span className="block text-muted-foreground">
                    {t(`roles.${invitation.role}`)},{" "}
                    {t("members.expires", {
                      date: format.dateTime(new Date(invitation.expires_at), { dateStyle: "medium" }),
                    })}
                  </span>
                </span>
                <Button variant="ghost" size="sm" disabled={cancel.pending} onClick={() => cancel.run(invitation.id)}>
                  {t("members.cancelInvitation")}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </SectionCard>
  );
}

/** Page « Organisation » (acheteur) et « Profil » (fournisseur). */
export function OrganizationScreen() {
  const t = useTranslations();
  const me = useMe().data;
  if (!me) return null;
  return (
    <div className="space-y-5">
      <PageHeading title={t("org.title")} description={me.organization.name} />
      <ProfileCard canEdit={me.permissions.includes("organization:update")} />
      <DocumentsCard canUpload={me.permissions.includes("document:upload")} />
      {me.permissions.includes("member:invite") && <MembersCard kind={me.organization.kind} />}
    </div>
  );
}

/** Page interne « Utilisateurs et permissions » : les collaborateurs SOON TRADE. */
export function InternalUsersScreen() {
  const t = useTranslations();
  const me = useMe().data;
  if (!me) return null;
  return (
    <div className="space-y-5">
      <PageHeading title={t("nav.users")} description={me.organization.name} />
      {me.permissions.includes("member:invite") ? (
        <MembersCard kind="internal" />
      ) : (
        <FormMessage tone="error">{t("common.forbidden")}</FormMessage>
      )}
    </div>
  );
}
