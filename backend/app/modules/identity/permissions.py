"""Rôles et permissions (docs/security/roles-permissions.md).

shortcut: la correspondance rôle -> permissions vit dans le code ; la déplacer en base
quand les administrateurs devront la modifier eux-mêmes (Phase 11).

Seules les permissions utilisées par les modules déjà livrés figurent ici ; chaque
module ajoute les siennes en arrivant.
"""

from typing import Literal

Kind = Literal["buyer", "supplier", "internal"]

ROLE_KIND: dict[str, Kind] = {
    "buyer_owner": "buyer",
    "buyer_member": "buyer",
    "supplier_owner": "supplier",
    "supplier_member": "supplier",
    "admin": "internal",
    "sourcing_agent": "internal",
    "sales_agent": "internal",
    "finance_agent": "internal",
    "logistics_agent": "internal",
    "support_agent": "internal",
    "auditor": "internal",
}

OWNER_ROLE: dict[Kind, str] = {"buyer": "buyer_owner", "supplier": "supplier_owner", "internal": "admin"}

MEMBER_INVITE = "member:invite"  # inviter, lister et gérer les membres de sa propre organisation
ORGANIZATION_UPDATE = "organization:update"  # modifier le profil de sa propre organisation
ORGANIZATION_CREATE_BUYER = "organization:create:buyer"
ORGANIZATION_CREATE_SUPPLIER = "organization:create:supplier"
ORGANIZATION_READ_ALL = "organization:read"  # annuaire interne des acheteurs et fournisseurs
SUPPLIER_VERIFY = "supplier:verify"
CATEGORY_MANAGE = "category:manage"
PRODUCT_MANAGE = "product:manage"  # catalogue de sa propre organisation fournisseur
CATALOG_READ_ALL = "catalog:read"  # consulter le catalogue de n'importe quel fournisseur
DOCUMENT_UPLOAD = "document:upload"  # déposer un document pour sa propre organisation
DOCUMENT_READ_ALL = "document:read"  # consulter les documents de n'importe quelle organisation
DOCUMENT_REVIEW = "document:review"
PURCHASE_REQUEST_MANAGE = "purchase_request:manage"  # créer et suivre les demandes de sa propre organisation
PURCHASE_REQUEST_READ_ALL = "purchase_request:read"  # consulter toutes les demandes (interne)
PURCHASE_REQUEST_QUALIFY = "purchase_request:qualify"  # qualifier, rejeter, demander des précisions
SOURCING_READ = "sourcing:read"
# ouvrir un dossier, assigner, présélectionner, annoter, solliciter, arbitrer les offres
SOURCING_MANAGE = "sourcing:manage"
SOLICITATION_RESPOND = "solicitation:respond"  # répondre aux sollicitations de sa propre organisation
PROPOSAL_READ_ALL = "proposal:read"  # consulter toutes les propositions (interne)
PROPOSAL_MANAGE = "proposal:manage"  # préparer, modifier, soumettre à validation, annuler
PROPOSAL_VALIDATE = "proposal:validate"  # valider et envoyer, ou renvoyer en préparation
PROPOSAL_VIEW = "proposal:view"  # consulter les propositions reçues par sa propre organisation
PROPOSAL_DECIDE = "proposal:decide"  # accepter, refuser, demander une modification
ORDER_READ_ALL = "order:read"  # commandes, bons fournisseurs et livraisons (interne)
ORDER_MANAGE = "order:manage"  # confirmer, annuler, clôturer une commande
LOGISTICS_MANAGE = "logistics:manage"  # préparer, planifier et suivre les livraisons, preuves, incidents
ORDER_VIEW = "order:view"  # commandes et livraisons de sa propre organisation acheteuse
DELIVERY_CONFIRM = "delivery:confirm"  # confirmer la réception d'une livraison de sa commande
SUPPLIER_ORDER_VIEW = "supplier_order:view"  # bons de commande de sa propre organisation fournisseur
DELIVERY_UPDATE = "delivery:update"  # faire avancer les livraisons de ses propres bons de commande
CLAIM_CREATE = "claim:create"  # ouvrir et suivre les réclamations de sa propre organisation
CLAIM_READ_ALL = "claim:read"
CLAIM_HANDLE = "claim:handle"  # prendre une réclamation en charge
CLAIM_DECIDE = "claim:decide"  # résoudre, rejeter, clôturer
CONVERSATION_USE = "conversation:use"  # écrire à SOON TRADE, au nom de sa propre organisation
CONVERSATION_READ_ALL = "conversation:read"
CONVERSATION_REPLY = "conversation:reply"  # répondre, écrire à un client, notes internes
CRM_NOTE = "crm:note"  # notes de suivi de la relation client
REPORT_READ = "report:read"  # rapports commerciaux et montants agrégés
REPORT_EXPORT = "report:export"  # exports CSV des données de l'activité
AUDIT_READ = "audit:read"

_OWNER = {MEMBER_INVITE, ORGANIZATION_UPDATE}
_BUYER = {
    DOCUMENT_UPLOAD,
    PURCHASE_REQUEST_MANAGE,
    PROPOSAL_VIEW,
    ORDER_VIEW,
    DELIVERY_CONFIRM,
    CLAIM_CREATE,
    CONVERSATION_USE,
}
_SUPPLIER = {
    DOCUMENT_UPLOAD,
    PRODUCT_MANAGE,
    SOLICITATION_RESPOND,
    SUPPLIER_ORDER_VIEW,
    DELIVERY_UPDATE,
    CONVERSATION_USE,
}
# Socle de tout collaborateur interne.
_STAFF = {
    ORGANIZATION_READ_ALL,
    PURCHASE_REQUEST_READ_ALL,
    ORDER_READ_ALL,
    CLAIM_READ_ALL,
    CONVERSATION_READ_ALL,
}
# Tout collaborateur qui agit (l'auditeur lit seulement) écrit aux clients et annote la relation.
_ACTS = {CONVERSATION_REPLY, CRM_NOTE}
_SOURCING = (
    _STAFF
    | {
        ORGANIZATION_CREATE_SUPPLIER,
        SUPPLIER_VERIFY,
        CATEGORY_MANAGE,
        CATALOG_READ_ALL,
        DOCUMENT_READ_ALL,
        DOCUMENT_REVIEW,
        PURCHASE_REQUEST_QUALIFY,
        SOURCING_READ,
        SOURCING_MANAGE,
        PROPOSAL_READ_ALL,
    }
    | _ACTS
)
_SALES = (
    _STAFF
    | {
        ORGANIZATION_CREATE_BUYER,
        CATALOG_READ_ALL,
        DOCUMENT_READ_ALL,
        SOURCING_READ,
        PROPOSAL_READ_ALL,
        PROPOSAL_MANAGE,
        PROPOSAL_VALIDATE,
        ORDER_MANAGE,
        REPORT_READ,
    }
    | _ACTS
)
# Les preuves de livraison se déposent sur la livraison même, jamais par le dépôt libre de documents.
_LOGISTICS = _STAFF | _ACTS | {LOGISTICS_MANAGE, CLAIM_HANDLE}
_SUPPORT = _STAFF | _ACTS | {CLAIM_HANDLE, CLAIM_DECIDE}

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    # À VALIDER : seul le propriétaire du compte acheteur engage l'organisation sur une proposition.
    "buyer_owner": frozenset(_OWNER | _BUYER | {PROPOSAL_DECIDE}),
    "buyer_member": frozenset(_BUYER),
    "supplier_owner": frozenset(_OWNER | _SUPPLIER),
    "supplier_member": frozenset(_SUPPLIER),
    "admin": frozenset(_OWNER | _SOURCING | _SALES | _LOGISTICS | _SUPPORT | {AUDIT_READ, REPORT_EXPORT}),
    "sourcing_agent": frozenset(_SOURCING),
    "sales_agent": frozenset(_SALES),
    # À VALIDER : exports réservés à la finance, à l'administrateur et à l'auditeur.
    "finance_agent": frozenset(_STAFF | _ACTS | {PROPOSAL_READ_ALL, REPORT_READ, REPORT_EXPORT}),
    "logistics_agent": frozenset(_LOGISTICS),
    "support_agent": frozenset(_SUPPORT),
    "auditor": frozenset(
        _STAFF
        | {
            CATALOG_READ_ALL,
            DOCUMENT_READ_ALL,
            SOURCING_READ,
            PROPOSAL_READ_ALL,
            AUDIT_READ,
            REPORT_READ,
            REPORT_EXPORT,
        }
    ),
}


def permissions_for(role: str) -> frozenset[str]:
    return ROLE_PERMISSIONS.get(role, frozenset())
