import { type ComponentProps, type ReactNode, useId } from "react";
import { cn } from "@/lib/utils";

const control =
  "w-full rounded-control border border-border bg-surface px-3 text-foreground placeholder:text-muted-foreground disabled:opacity-60";

function Labelled({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-semibold">
        {label}
      </label>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="mt-1.5 text-sm text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}

type Extra = { label: string; hint?: string };

/** Champ de formulaire avec libellé visible et aide associée pour les lecteurs d'écran. */
export function Field({ label, hint, className, ...props }: ComponentProps<"input"> & Extra) {
  const id = useId();
  return (
    <Labelled id={id} label={label} hint={hint}>
      <input id={id} aria-describedby={hint ? `${id}-hint` : undefined} className={cn(control, "h-11", className)} {...props} />
    </Labelled>
  );
}

export function SelectField({ label, hint, className, ...props }: ComponentProps<"select"> & Extra) {
  const id = useId();
  return (
    <Labelled id={id} label={label} hint={hint}>
      <select id={id} aria-describedby={hint ? `${id}-hint` : undefined} className={cn(control, "h-11", className)} {...props} />
    </Labelled>
  );
}

export function TextareaField({ label, hint, className, ...props }: ComponentProps<"textarea"> & Extra) {
  const id = useId();
  return (
    <Labelled id={id} label={label} hint={hint}>
      <textarea id={id} rows={3} aria-describedby={hint ? `${id}-hint` : undefined} className={cn(control, "py-2", className)} {...props} />
    </Labelled>
  );
}

/** Retour après une action : succès annoncé poliment, erreur annoncée immédiatement. */
export function FormMessage({ tone, children }: { tone: "success" | "error"; children: ReactNode }) {
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "rounded-control px-3 py-2 text-sm font-medium",
        tone === "error" ? "bg-danger-soft text-danger-foreground" : "bg-success-soft text-success-foreground",
      )}
    >
      {children}
    </p>
  );
}
