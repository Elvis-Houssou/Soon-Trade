"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, FormMessage, TextareaField } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

const PROFILES = ["buyer", "supplier", "other"] as const;

/** Formulaire public : un acheteur ou un fournisseur intéressé écrit à SOON TRADE. */
export function ContactForm() {
  const t = useTranslations("contact");
  const locale = useLocale();
  const [profile, setProfile] = useState<(typeof PROFILES)[number]>("supplier");
  const [state, setState] = useState<"idle" | "pending" | "sent" | "error" | "limited">("idle");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;
    setState("pending");
    try {
      await api("/contact", { ...data, profile, locale });
      setState("sent");
    } catch (error) {
      setState(error instanceof ApiError && error.status === 429 ? "limited" : "error");
    }
  }

  if (state === "sent") return <FormMessage tone="success">{t("sent")}</FormMessage>;

  return (
    <form onSubmit={onSubmit} className="space-y-4 rounded-card border border-border bg-surface p-5 sm:p-6">
      <fieldset>
        <legend className="mb-1.5 text-sm font-semibold">{t("profile")}</legend>
        <div className="flex flex-wrap gap-2">
          {PROFILES.map((value) => (
            <label
              key={value}
              className={cn(
                "cursor-pointer rounded-full border px-4 py-2 text-sm font-semibold transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary",
                profile === value
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border hover:bg-primary-soft",
              )}
            >
              <input
                type="radio"
                name="profile-choice"
                value={value}
                checked={profile === value}
                onChange={() => setProfile(value)}
                className="sr-only"
              />
              {t(`profiles.${value}`)}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("name")} name="name" autoComplete="name" required minLength={2} maxLength={120} />
        <Field label={t("company")} name="company" autoComplete="organization" maxLength={160} />
        <Field label={t("email")} name="email" type="email" autoComplete="email" required />
        <Field label={t("phone")} name="phone" type="tel" autoComplete="tel" maxLength={40} />
      </div>
      <TextareaField
        label={t("message")}
        hint={t(`messageHint.${profile}`)}
        name="message"
        rows={5}
        required
        minLength={10}
        maxLength={3000}
      />
      {/* Piège à robots : invisible et ignoré par les humains comme par les lecteurs d'écran. */}
      <input type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden className="hidden" />
      {(state === "error" || state === "limited") && (
        <FormMessage tone="error">{t(state === "limited" ? "limited" : "error")}</FormMessage>
      )}
      <Button type="submit" size="lg" disabled={state === "pending"}>
        {t(state === "pending" ? "sending" : "submit")}
      </Button>
    </form>
  );
}
