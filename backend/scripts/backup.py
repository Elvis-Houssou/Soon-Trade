# ruff: noqa: S603 - commandes aux arguments fixes, sans shell ; le nom de base est validé
"""Sauvegarde et restauration de la base PostgreSQL (Phase 12).

    python scripts/backup.py save                    # base locale -> backups/soontrade-AAAAMMJJ-HHMMSS.dump
    python scripts/backup.py restore FICHIER         # -> base locale « soontrade_restore », puis contrôle
    python scripts/backup.py restore FICHIER --into NOM

Tout passe par le conteneur PostgreSQL de infra/compose.yaml : rien à installer. En
production, la sauvegarde continue de l'hébergeur (Neon, PITR) reste la première ligne ;
ce script sert aux copies hors hébergeur et aux exercices de restauration
(docs/operations/sauvegardes.md).
"""

import argparse
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "-f", str(ROOT / "infra" / "compose.yaml")]
USER, SOURCE = "soontrade", "soontrade"
BACKUPS = ROOT / "backups"


def _psql(database: str, sql: str) -> str:
    result = subprocess.run(
        [*COMPOSE, "exec", "-T", "postgres", "psql", "-U", USER, "-d", database, "-At", "-c", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def save() -> Path:
    BACKUPS.mkdir(exist_ok=True)
    target = BACKUPS / f"soontrade-{datetime.now(UTC):%Y%m%d-%H%M%S}.dump"
    with target.open("wb") as out:
        # Format personnalisé : compressé, restaurable table par table.
        subprocess.run(
            [*COMPOSE, "exec", "-T", "postgres", "pg_dump", "-U", USER, "-d", SOURCE, "-Fc", "--no-owner"],
            check=True,
            stdout=out,
        )
    print(f"Sauvegarde : {target} ({target.stat().st_size} octets)")
    return target


def restore(dump: Path, into: str) -> None:
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", into):
        sys.exit("Nom de base invalide.")
    if into == SOURCE:
        sys.exit("Refusé : la restauration ne remplace jamais la base de travail. Choisissez un autre nom.")
    _psql("postgres", f'DROP DATABASE IF EXISTS "{into}"')
    _psql("postgres", f'CREATE DATABASE "{into}"')
    with dump.open("rb") as data:
        subprocess.run(
            [
                *COMPOSE,
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "-U",
                USER,
                "-d",
                into,
                "--no-owner",
                "--exit-on-error",
            ],
            check=True,
            stdin=data,
        )
    # Contrôle : même version de schéma et mêmes volumes que la base d'origine.
    checks = {
        "version Alembic": "SELECT version_num FROM alembic_version",
        "comptes": "SELECT count(*) FROM users",
        "demandes": "SELECT count(*) FROM purchase_requests",
        "commandes": "SELECT count(*) FROM orders",
        "journal d'audit": "SELECT count(*) FROM audit_logs",
    }
    failed = False
    for label, sql in checks.items():
        restored, original = _psql(into, sql), _psql(SOURCE, sql)
        status = "OK " if restored == original else "ÉCART"
        failed |= restored != original
        print(f"{status} {label} : {restored} (origine : {original})")
    if failed:
        sys.exit("La copie restaurée diffère de la base d'origine (normal si celle-ci a changé depuis).")
    print(f"Restauration vérifiée dans « {into} ».")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("save")
    restoring = commands.add_parser("restore")
    restoring.add_argument("dump", type=Path)
    restoring.add_argument("--into", default="soontrade_restore")
    args = parser.parse_args()
    if args.command == "save":
        save()
    else:
        restore(args.dump, args.into)


if __name__ == "__main__":
    main()
