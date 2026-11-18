"""Test de charge adapté (Phase 12) : une plateforme B2B, pas un site grand public.

    python scripts/load_test.py .env [--users 20] [--seconds 30] [--api http://127.0.0.1:8000]

Hypothèse de dimensionnement (À VALIDER) : quelques dizaines d'utilisateurs simultanés.
Chaque utilisateur virtuel, connecté avec un compte de démonstration, enchaîne les lectures
les plus fréquentes : tableau de bord, notifications, demandes, commandes. Le script rend
les latences (médiane, 95e centile, maximum) et le taux d'erreur, puis échoue au-delà des
seuils fixés ci-dessous. Le mot de passe de démonstration est lu dans le fichier et jamais affiché.
"""

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

import httpx

# Seuils d'acceptation (À VALIDER) pour une instance de préproduction.
P95_MAX_MS = 800
ERROR_RATE_MAX = 0.01
ACCOUNTS = ("acheteur@demo.soontrade.com", "commercial@demo.soontrade.com", "fournisseur@demo.soontrade.com")
READS = {
    "acheteur": ("/dashboard", "/notifications", "/purchase-requests", "/orders"),
    "commercial": ("/dashboard", "/notifications", "/internal/purchase-requests", "/internal/orders"),
    "fournisseur": ("/dashboard", "/notifications", "/solicitations", "/supplier-orders"),
}


async def user(
    api: str, email: str, password: str, deadline: float, timings: list[tuple[str, float]], errors: list[str]
) -> None:
    async with httpx.AsyncClient(base_url=api, timeout=15) as client:
        try:
            login = await client.post("/auth/login", json={"email": email, "password": password})
        except httpx.HTTPError as error:
            errors.append(f"connexion {type(error).__name__}")
            return
        if login.status_code != 200:
            errors.append(f"connexion {login.status_code}")
            return
        paths = READS[email.split("@")[0]]
        while time.perf_counter() < deadline:
            for path in paths:
                started = time.perf_counter()
                try:
                    response = await client.get(path)
                    if response.status_code >= 400:
                        errors.append(f"{path} {response.status_code}")
                except httpx.HTTPError as error:
                    errors.append(f"{path} {type(error).__name__}")
                timings.append((path, (time.perf_counter() - started) * 1000))


async def run(api: str, password: str, users: int, seconds: int) -> int:
    timings: list[tuple[str, float]] = []
    errors: list[str] = []
    deadline = time.perf_counter() + seconds
    await asyncio.gather(
        *(user(api, ACCOUNTS[i % len(ACCOUNTS)], password, deadline, timings, errors) for i in range(users))
    )
    if not timings:
        print("Aucune requête mesurée.", errors[:5])
        return 1
    ordered = sorted(ms for _, ms in timings)
    p95 = ordered[int(len(ordered) * 0.95) - 1]
    error_rate = len(errors) / (len(timings) + len(errors))
    print(f"{users} utilisateurs, {seconds} s : {len(timings)} requêtes ({len(timings) / seconds:.0f}/s)")
    print(
        f"latence médiane {statistics.median(ordered):.0f} ms · "
        f"95e centile {p95:.0f} ms · max {ordered[-1]:.0f} ms"
    )
    print(f"erreurs : {len(errors)} ({error_rate:.2%})" + (f", ex. {errors[:3]}" if errors else ""))
    by_path: dict[str, list[float]] = {}
    for path, ms in timings:
        by_path.setdefault(path, []).append(ms)
    for path, values in sorted(by_path.items(), key=lambda kv: -statistics.median(kv[1])):
        print(f"  {path:<32} médiane {statistics.median(values):>5.0f} ms · max {max(values):>5.0f} ms")
    ok = p95 <= P95_MAX_MS and error_rate <= ERROR_RATE_MAX
    print(
        "RÉUSSI" if ok else f"ÉCHEC : seuils {P95_MAX_MS} ms au 95e centile, {ERROR_RATE_MAX:.0%} d'erreurs"
    )
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("env_file", type=Path)
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    lines = args.env_file.read_text(encoding="utf-8").splitlines()
    password = next(line.split("=", 1)[1].strip() for line in lines if line.startswith("SEED_PASSWORD="))
    sys.exit(asyncio.run(run(args.api, password, args.users, args.seconds)))


if __name__ == "__main__":
    main()
