import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

// Liens et navigation qui conservent la langue courante dans l'URL.
export const { Link, usePathname, useRouter, redirect } = createNavigation(routing);
