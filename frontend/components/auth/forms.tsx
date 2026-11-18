"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FormEvent, type ReactNode, useState } from "react";
import { type Me, useEnterSpace } from "@/components/auth/session";
import { Shake } from "@/components/motion/public-motion";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Link } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api";

// shortcut: validation native du navigateur + réponse de l'API ; passer à
// React Hook Form et Zod avec les formulaires métier (Phase 5).

/** Soumet le formulaire, bloque le bouton pendant l'appel et traduit l'erreur. */
function useSubmit<T>(action: (data: Record<string, string>) => Promise<T>, messageFor: (error: ApiError) => string) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string>();
  const [result, setResult] = useState<T>();

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;
    setPending(true);
    setError(undefined);
    try {
      setResult(await action(data));
    } catch (caught) {
      setError(messageFor(caught instanceof ApiError ? caught : new ApiError(0, "unknown_error")));
    } finally {
      setPending(false);
    }
  }
  return { onSubmit, pending, error, done: result !== undefined };
}

function AuthForm({
  title,
  intro,
  submit,
  state,
  footer,
  children,
}: {
  title: string;
  intro?: ReactNode;
  submit: string;
  state: { onSubmit: (event: FormEvent<HTMLFormElement>) => void; pending: boolean; error?: string };
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <form onSubmit={state.onSubmit} className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">{title}</h1>
        {intro && <p className="mt-2 text-muted-foreground">{intro}</p>}
      </div>
      {children}
      {state.error && (
        <Shake trigger={state.error}>
          <p role="alert" className="rounded-control bg-danger-soft px-3 py-2 text-sm font-medium text-danger-foreground">
            {state.error}
          </p>
        </Shake>
      )}
      <Button type="submit" size="lg" className="w-full" disabled={state.pending}>
        {submit}
      </Button>
      {footer && <p className="text-center text-sm">{footer}</p>}
    </form>
  );
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="text-muted-foreground">
      {children}
    </p>
  );
}

function BackToLogin() {
  const t = useTranslations("auth");
  return (
    <Link href="/connexion" className="font-semibold text-primary-soft-foreground hover:underline">
      {t("backToLogin")}
    </Link>
  );
}

export function LoginForm() {
  const t = useTranslations("auth");
  const enterSpace = useEnterSpace();
  const state = useSubmit(
    async ({ email, password }) => enterSpace(await api<Me>("/auth/login", { email, password })),
    (error) => t(error.status === 401 ? "loginInvalid" : error.status === 429 ? "loginLocked" : "genericError"),
  );

  return (
    <AuthForm
      title={t("loginTitle")}
      intro={t("loginIntro")}
      submit={t("loginSubmit")}
      state={state}
      footer={
        <Link href="/mot-de-passe" className="font-semibold text-primary-soft-foreground hover:underline">
          {t("forgotLink")}
        </Link>
      }
    >
      <Field label={t("email")} name="email" type="email" autoComplete="username" required />
      <Field label={t("password")} name="password" type="password" autoComplete="current-password" required />
    </AuthForm>
  );
}

export function AcceptInvitationForm() {
  const t = useTranslations("auth");
  const tCommon = useTranslations("common");
  const { token } = useParams<{ token: string }>();
  const enterSpace = useEnterSpace();
  const invitation = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => api<{ email: string; organization_name: string }>(`/invitations/${token}`),
  });
  const state = useSubmit(
    async ({ full_name, password }) =>
      enterSpace(await api<Me>(`/invitations/${token}/accept`, { full_name, password })),
    (error) => t(error.status === 404 ? "inviteInvalid" : error.status === 409 ? "inviteExists" : "genericError"),
  );

  if (invitation.isPending) return <Notice>{tCommon("loading")}</Notice>;
  if (invitation.error) {
    const notFound = invitation.error instanceof ApiError && invitation.error.status === 404;
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold">{t("inviteTitle")}</h1>
        <p role="alert">{t(notFound ? "inviteInvalid" : "genericError")}</p>
        <BackToLogin />
      </div>
    );
  }

  return (
    <AuthForm
      title={t("inviteTitle")}
      intro={t("inviteIntro", { organization: invitation.data.organization_name, email: invitation.data.email })}
      submit={t("inviteSubmit")}
      state={state}
    >
      <Field label={t("fullName")} name="full_name" autoComplete="name" minLength={2} maxLength={200} required />
      <Field
        label={t("password")}
        name="password"
        type="password"
        autoComplete="new-password"
        minLength={10}
        maxLength={128}
        hint={t("passwordHint")}
        required
      />
    </AuthForm>
  );
}

export function ForgotPasswordForm() {
  const t = useTranslations("auth");
  const state = useSubmit(
    async ({ email }) => api("/auth/password/forgot", { email }).then(() => true),
    () => t("genericError"),
  );

  if (state.done) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold">{t("forgotTitle")}</h1>
        <Notice>{t("forgotSent")}</Notice>
        <BackToLogin />
      </div>
    );
  }
  return (
    <AuthForm
      title={t("forgotTitle")}
      intro={t("forgotIntro")}
      submit={t("forgotSubmit")}
      state={state}
      footer={<BackToLogin />}
    >
      <Field label={t("email")} name="email" type="email" autoComplete="username" required />
    </AuthForm>
  );
}

export function ResetPasswordForm() {
  const t = useTranslations("auth");
  const { token } = useParams<{ token: string }>();
  const state = useSubmit(
    async ({ password }) => api("/auth/password/reset", { token, password }).then(() => true),
    (error) => t(error.status === 404 ? "resetInvalid" : "genericError"),
  );

  if (state.done) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold">{t("resetTitle")}</h1>
        <Notice>{t("resetDone")}</Notice>
        <BackToLogin />
      </div>
    );
  }
  return (
    <AuthForm title={t("resetTitle")} submit={t("resetSubmit")} state={state} footer={<BackToLogin />}>
      <Field
        label={t("newPassword")}
        name="password"
        type="password"
        autoComplete="new-password"
        minLength={10}
        maxLength={128}
        hint={t("passwordHint")}
        required
      />
    </AuthForm>
  );
}
