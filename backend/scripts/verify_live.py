"""Vérification de bout en bout contre l'API, PostgreSQL et le stockage S3 réellement lancés."""

import sys
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000"
lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
password = next(line.split("=", 1)[1].strip() for line in lines if line.startswith("SEED_PASSWORD="))
results = []


def check(label, condition, detail=""):
    results.append(condition)
    print(("OK   " if condition else "ECHEC"), label, detail if not condition else "")


def login(email):
    client = httpx.Client(base_url=API, timeout=20)
    response = client.post("/auth/login", json={"email": email, "password": password})
    check(f"connexion {email}", response.status_code == 200, response.text[:120])
    return client


check(
    "API prete, base connectee", httpx.get(f"{API}/health/ready").json() == {"status": "ok", "database": "up"}
)
admin, sourcing = login("admin@demo.soontrade.com"), login("sourcing@demo.soontrade.com")
buyer, supplier, rival = (
    login(f"{n}@demo.soontrade.com") for n in ("acheteur", "fournisseur", "fournisseur2")
)

me = supplier.get("/auth/me").json()
check(
    "espace fournisseur",
    me["organization"]["kind"] == "supplier" and me["organization"]["name"] == "Sodeci Agro",
)

products = supplier.get("/products").json()
check("catalogue fournisseur : 4 produits", len(products) == 4, str(len(products)))
check("catalogue du concurrent vide", rival.get("/products").json() == [])
check("acheteur refuse sur le catalogue", buyer.get("/products").status_code == 403)

category = next(c for c in admin.get("/categories").json() if c["name"] == "Huiles")
created = supplier.post(
    "/products",
    json={
        "name": "Huile de palme (test e2e)",
        "category_id": category["id"],
        "unit": "litre",
        "available_quantity": "10000",
    },
)
check("creation d'un produit", created.status_code == 201, created.text[:120])
pid = created.json()["id"]
check(
    "le concurrent ne peut pas le modifier",
    rival.patch(f"/products/{pid}", json={"name": "x y"}).status_code == 404,
)
check("retrait du produit", supplier.delete(f"/products/{pid}").status_code == 204)

suppliers = sourcing.get("/organizations", params={"kind": "supplier"}).json()
banana = next(o for o in suppliers if o["name"].startswith("Coop"))
check("annuaire interne : 2 fournisseurs", len(suppliers) == 2, str(len(suppliers)))
verified = sourcing.post(
    f"/organizations/{banana['id']}/verification", json={"status": "verified", "note": "test e2e"}
)
check(
    "verification par le sourcing",
    verified.status_code == 200 and verified.json()["verification_status"] == "verified",
)
profile = rival.get("/organization").json()
check(
    "le fournisseur voit son statut, pas la note",
    profile["verification_status"] == "verified" and "verification_note" not in profile,
)
sourcing.post(f"/organizations/{banana['id']}/verification", json={"status": "pending"})
sodeci = next(o for o in suppliers if o["name"] == "Sodeci Agro")
check(
    "le sourcing lit le catalogue d'un fournisseur",
    len(sourcing.get(f"/organizations/{sodeci['id']}/products").json()) == 4,
)

pdf = b"%PDF-1.7\n% document de test e2e\n"
uploaded = supplier.post(
    "/documents",
    data={"doc_type": "company_registration"},
    files={"file": ("rccm-test.pdf", pdf, "application/pdf")},
)
check("depot d'un document", uploaded.status_code == 201, uploaded.text[:160])
if uploaded.status_code == 201:
    did = uploaded.json()["id"]
    link = supplier.get(f"/documents/{did}/url").json()
    downloaded = httpx.get(link["url"], timeout=20)
    check(
        "telechargement par lien pre-signe (S3 local)",
        downloaded.status_code == 200 and downloaded.content == pdf,
        str(downloaded.status_code),
    )
    check("document invisible du concurrent", rival.get(f"/documents/{did}/url").status_code == 404)
    check("document invisible de l'acheteur", buyer.get(f"/documents/{did}/url").status_code == 404)
    check(
        "le sourcing le voit et le valide",
        sourcing.post(f"/documents/{did}/review", json={"status": "approved"}).status_code == 200,
    )
    check(
        "faux PDF refuse",
        supplier.post(
            "/documents",
            data={"doc_type": "other"},
            files={"file": ("x.pdf", b"MZ pas un pdf", "application/pdf")},
        ).status_code
        == 400,
    )

# --- Phase 5 : de la demande d'achat au dossier de sourcing ---
need = {
    "product_name": "Riz blanc (test e2e)",
    "quantity": "40",
    "unit": "tonne",
    "delivery_location": "Abidjan",
}
draft = buyer.post("/purchase-requests", json=need)
check("l'acheteur cree un brouillon", draft.status_code == 201, draft.text[:160])
rid = draft.json()["id"]
check(
    "brouillon invisible de l'equipe interne",
    sourcing.get(f"/internal/purchase-requests/{rid}").status_code == 404,
)
check("l'acheteur soumet", buyer.post(f"/purchase-requests/{rid}/submit").json().get("status") == "submitted")
check("demande invisible du fournisseur", supplier.get(f"/purchase-requests/{rid}").status_code == 403)
check(
    "le fournisseur ne voit aucune demande interne",
    supplier.get("/internal/purchase-requests").status_code == 403,
)
asked = sourcing.post(
    f"/internal/purchase-requests/{rid}/request-info", json={"message": "Quel taux de brisure ?"}
)
check(
    "le sourcing demande une precision",
    asked.status_code == 200 and asked.json()["status"] == "info_requested",
)
mine = buyer.get(f"/purchase-requests/{rid}").json()
check("l'acheteur lit la question", mine["history"][-1]["message"] == "Quel taux de brisure ?")
buyer.patch(f"/purchase-requests/{rid}", json={"specifications": "5 % de brisure"})
answered = buyer.post(f"/purchase-requests/{rid}/submit", json={"message": "5 % maximum"})
check("l'acheteur repond", answered.status_code == 200 and answered.json()["status"] == "submitted")
check(
    "pas de dossier sans qualification",
    sourcing.post("/sourcing/cases", json={"request_id": rid}).status_code == 409,
)
check(
    "le commercial ne peut pas qualifier",
    login("commercial@demo.soontrade.com").post(f"/internal/purchase-requests/{rid}/qualify").status_code
    == 403,
)
check(
    "le sourcing qualifie",
    sourcing.post(f"/internal/purchase-requests/{rid}/qualify").json().get("status") == "qualified",
)
opened = sourcing.post("/sourcing/cases", json={"request_id": rid})
check(
    "ouverture du dossier de sourcing",
    opened.status_code == 201 and opened.json()["reference"].startswith("ST-SRC-"),
    opened.text[:160],
)
check(
    "un seul dossier par demande",
    sourcing.post("/sourcing/cases", json={"request_id": rid}).status_code == 409,
)
cid = opened.json()["id"]
found = sourcing.get("/sourcing/suppliers", params={"q": "riz"}).json()
check(
    "recherche : fournisseurs verifies uniquement",
    bool(found) and {p["supplier"]["name"] for p in found} == {"Sodeci Agro"},
    str(found)[:160],
)
shortlisted = sourcing.post(f"/sourcing/cases/{cid}/candidates", json={"organization_id": sodeci["id"]})
check(
    "preselection d'un fournisseur",
    shortlisted.status_code == 201 and len(shortlisted.json()["candidates"]) == 1,
)
check(
    "fournisseur non verifie refuse",
    sourcing.post(f"/sourcing/cases/{cid}/candidates", json={"organization_id": banana["id"]}).status_code
    == 400,
)
noted = sourcing.post(f"/sourcing/cases/{cid}/notes", json={"body": "Note interne e2e : marge visee"})
check("note interne ajoutee", noted.status_code == 201 and len(noted.json()["notes"]) == 1)
seen = buyer.get(f"/purchase-requests/{rid}").text
check(
    "l'acheteur ne voit ni note, ni fournisseur, ni dossier, ni collaborateur",
    '"in_sourcing"' in seen
    and not any(s in seen for s in ("marge", "Sodeci", "ST-SRC", "Koffi", "actor", "notes")),
)
check("dossier invisible de l'acheteur", buyer.get(f"/sourcing/cases/{cid}").status_code == 403)
check(
    "dossier invisible du fournisseur preselectionne",
    supplier.get(f"/sourcing/cases/{cid}").status_code == 403,
)
check(
    "annulation par l'acheteur",
    buyer.post(f"/purchase-requests/{rid}/cancel").json().get("status") == "cancelled",
)
check(
    "le dossier d'une demande annulee est fige",
    sourcing.delete(f"/sourcing/cases/{cid}/candidates/{sodeci['id']}").status_code == 409,
)

# --- Phase 6 : sollicitations, offres et comparaison ---
from datetime import date, timedelta  # noqa: E402

need = {**need, "product_name": "Mais grain (test e2e)", "additional_info": "Pour Entreprise Traore"}
rid = buyer.post("/purchase-requests", json=need).json()["id"]
buyer.post(f"/purchase-requests/{rid}/submit")
sourcing.post(f"/internal/purchase-requests/{rid}/qualify")
cid = sourcing.post("/sourcing/cases", json={"request_id": rid}).json()["id"]
sourcing.post(f"/organizations/{banana['id']}/verification", json={"status": "verified"})
for org in (sodeci, banana):
    sourcing.post(f"/sourcing/cases/{cid}/candidates", json={"organization_id": org["id"]})
drafts = [
    sourcing.post(f"/sourcing/cases/{cid}/solicitations", json={"organization_id": org["id"]}).json()
    for org in (sodeci, banana)
]
check(
    "brouillons de sollicitation sans les informations libres de l'acheteur",
    all(d.get("status") == "draft" and "Traore" not in str(d) for d in drafts),
)
check(
    "brouillon invisible du fournisseur", supplier.get(f"/solicitations/{drafts[0]['id']}").status_code == 404
)
sent = [sourcing.post(f"/sourcing/solicitations/{d['id']}/send").json() for d in drafts]
check("envoi des sollicitations", all(s.get("status") == "sent" for s in sent))
mine = supplier.get(f"/solicitations/{sent[0]['id']}").json()
check("le fournisseur ouvre sa sollicitation", mine.get("status") == "viewed")
check(
    "le fournisseur ne voit ni l'acheteur, ni le dossier, ni le concurrent",
    not any(s in str(mine) for s in ("Traore", "ST-SRC", "ST-ACH", "Banana", "Koffi")),
)
check(
    "sollicitation invisible du concurrent", rival.get(f"/solicitations/{sent[0]['id']}").status_code == 404
)
check("sollicitations refusees a l'acheteur", buyer.get("/solicitations").status_code == 403)
valid = (date.today() + timedelta(days=15)).isoformat()
offer = {"unit_price": "185000", "quantity": "40", "lead_time_days": 10, "valid_until": valid}
answered = supplier.post(f"/solicitations/{sent[0]['id']}/offer", json=offer)
check("offre du fournisseur", answered.status_code == 201, answered.text[:160])
revised = supplier.put(f"/solicitations/{sent[0]['id']}/offer", json={**offer, "unit_price": "180000"})
check("nouvelle version de l'offre", len(revised.json().get("offer", {}).get("versions", [])) == 2)
rival_offer = rival.post(f"/solicitations/{sent[1]['id']}/offer", json={**offer, "unit_price": "175000"})
check("offre du concurrent", rival_offer.status_code == 201)
check(
    "aucun prix concurrent cote fournisseur",
    "175000" not in supplier.get("/solicitations").text and "180000" not in rival.get("/solicitations").text,
)
compared = sourcing.get(f"/sourcing/cases/{cid}/solicitations").json()
prices = sorted(
    (s["offer"]["versions"][-1]["unit_price"], s["supplier_name"]) for s in compared if s["offer"]
)
check(
    "comparaison interne des deux offres",
    [n for _, n in prices] == ["Coopérative Banana", "Sodeci Agro"],
    str(prices),
)
oid = answered.json()["offer"]["id"]
check(
    "mise en analyse",
    sourcing.post(f"/sourcing/offers/{oid}/review").json()["offer"]["status"] == "under_review",
)
check(
    "offre en analyse non modifiable",
    supplier.put(f"/solicitations/{sent[0]['id']}/offer", json=offer).status_code == 409,
)
check(
    "offre retenue", sourcing.post(f"/sourcing/offers/{oid}/retain").json()["offer"]["status"] == "retained"
)
check(
    "l'acheteur ne voit aucune offre",
    not any(
        s in buyer.get(f"/purchase-requests/{rid}").text for s in ("185000", "180000", "ST-OFF", "Sodeci")
    ),
)
buyer.post(f"/purchase-requests/{rid}/cancel")
sourcing.post(f"/organizations/{banana['id']}/verification", json={"status": "pending"})

members = buyer.get("/members").json()
check(
    "acheteur : 2 membres, les siens uniquement",
    {m["email"] for m in members} == {"acheteur@demo.soontrade.com", "acheteur.membre@demo.soontrade.com"},
)
check("journal d'audit lisible par l'admin", admin.get("/audit").status_code == 200)
check("journal d'audit refuse a l'acheteur", buyer.get("/audit").status_code == 403)
check(
    "deconnexion",
    supplier.post("/auth/logout").status_code == 204 and supplier.get("/auth/me").status_code == 401,
)

print(f"\n{sum(results)}/{len(results)} verifications reussies")
sys.exit(0 if all(results) else 1)
