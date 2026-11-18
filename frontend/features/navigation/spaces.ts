import {
  BarChart3,
  Boxes,
  Building2,
  CircleAlert,
  CreditCard,
  FileText,
  Folder,
  HandCoins,
  Home,
  Inbox,
  Layers,
  LayoutGrid,
  type LucideIcon,
  Mail,
  MessageSquare,
  Package,
  Percent,
  PlusCircle,
  ScrollText,
  Search,
  Settings,
  ShoppingCart,
  Store,
  Tag,
  Truck,
  Users,
  UsersRound,
} from "lucide-react";

export type SpaceId = "buyer" | "supplier" | "internal";

export type NavItem = {
  /** Segment d'URL sous l'espace ; chaîne vide pour la vue d'ensemble. */
  slug: string;
  /** Clé du libellé dans messages/*.json, espace de noms `nav`. */
  key: string;
  icon: LucideIcon;
  /** Phase du plan de développement (README §26) qui livre cette section. */
  phase?: number;
  /** La section a sa propre page : plus de page d'attente générée. */
  live?: true;
  /** Permission sans laquelle l'entrée n'est pas affichée (l'API refuse de toute façon). */
  permission?: string;
};

export type Space = {
  id: SpaceId;
  icon: LucideIcon;
  nav: NavItem[];
};

/**
 * Navigation de référence (README §22). Elle sera filtrée selon les permissions
 * réelles renvoyées par l'API à partir de la Phase 3.
 */
export const SPACES: Record<SpaceId, Space> = {
  buyer: {
    id: "buyer",
    icon: ShoppingCart,
    nav: [
      { slug: "", key: "overview", icon: Home },
      { slug: "nouvelle-demande", key: "newRequest", icon: PlusCircle, live: true, permission: "purchase_request:manage" },
      { slug: "demandes", key: "requests", icon: Layers, live: true, permission: "purchase_request:manage" },
      { slug: "propositions", key: "proposals", icon: Tag, live: true, permission: "proposal:view" },
      { slug: "commandes", key: "orders", icon: Package, live: true, permission: "order:view" },
      { slug: "paiements", key: "payments", icon: CreditCard, phase: 9 },
      { slug: "livraisons", key: "deliveries", icon: Truck, live: true, permission: "order:view" },
      { slug: "messages", key: "messages", icon: MessageSquare, live: true, permission: "conversation:use" },
      { slug: "reclamations", key: "claims", icon: CircleAlert, live: true, permission: "claim:create" },
      { slug: "documents", key: "documents", icon: Folder, phase: 4 },
      { slug: "organisation", key: "organization", icon: Building2, live: true },
      { slug: "parametres", key: "settings", icon: Settings, phase: 3 },
    ],
  },
  supplier: {
    id: "supplier",
    icon: Store,
    nav: [
      { slug: "", key: "overview", icon: Home },
      { slug: "sollicitations", key: "solicitations", icon: Mail, live: true, permission: "solicitation:respond" },
      { slug: "offres", key: "offers", icon: Tag, live: true, permission: "solicitation:respond" },
      { slug: "catalogue", key: "catalog", icon: LayoutGrid, live: true },
      { slug: "disponibilites", key: "stock", icon: Boxes, phase: 4 },
      { slug: "commandes", key: "orders", icon: Package, live: true, permission: "supplier_order:view" },
      { slug: "livraisons", key: "deliveries", icon: Truck, live: true, permission: "supplier_order:view" },
      { slug: "versements", key: "supplierPayouts", icon: HandCoins, phase: 9 },
      { slug: "messages", key: "messages", icon: MessageSquare, live: true, permission: "conversation:use" },
      { slug: "documents", key: "documents", icon: Folder, phase: 4 },
      { slug: "profil", key: "profile", icon: Building2, live: true },
      { slug: "parametres", key: "settings", icon: Settings, phase: 3 },
    ],
  },
  internal: {
    id: "internal",
    icon: Layers,
    nav: [
      { slug: "", key: "overview", icon: Home },
      { slug: "demandes", key: "buyerRequests", icon: Inbox, live: true, permission: "purchase_request:read" },
      { slug: "sourcing", key: "sourcing", icon: Search, live: true, permission: "sourcing:read" },
      { slug: "acheteurs", key: "buyers", icon: Building2, live: true, permission: "organization:read" },
      { slug: "fournisseurs", key: "suppliers", icon: UsersRound, live: true, permission: "organization:read" },
      { slug: "sollicitations", key: "solicitations", icon: Mail, live: true, permission: "sourcing:read" },
      { slug: "offres", key: "receivedOffers", icon: Tag, live: true, permission: "sourcing:read" },
      { slug: "propositions", key: "buyerProposals", icon: FileText, live: true, permission: "proposal:read" },
      { slug: "commandes", key: "orders", icon: Package, live: true, permission: "order:read" },
      { slug: "paiements", key: "payments", icon: CreditCard, phase: 9 },
      { slug: "commissions", key: "commissions", icon: Percent, phase: 9 },
      { slug: "versements", key: "payouts", icon: HandCoins, phase: 9 },
      { slug: "logistique", key: "logistics", icon: Truck, live: true, permission: "order:read" },
      { slug: "reclamations", key: "claims", icon: CircleAlert, live: true, permission: "claim:read" },
      { slug: "messages", key: "messages", icon: MessageSquare, live: true, permission: "conversation:read" },
      { slug: "crm", key: "crm", icon: Building2, live: true, permission: "organization:read" },
      { slug: "documents", key: "documents", icon: Folder, phase: 4 },
      { slug: "rapports", key: "reports", icon: BarChart3, live: true, permission: "report:read" },
      { slug: "utilisateurs", key: "users", icon: Users, live: true, permission: "member:invite" },
      { slug: "parametres", key: "settings", icon: Settings, live: true, permission: "category:manage" },
      { slug: "audit", key: "audit", icon: ScrollText, live: true, permission: "audit:read" },
    ],
  },
};

export function hrefFor(space: SpaceId, slug: string) {
  return slug ? `/${space}/${slug}` : `/${space}`;
}
