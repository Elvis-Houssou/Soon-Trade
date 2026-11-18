import hashlib
import secrets

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()  # Argon2id


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


# Vérifié quand l'adresse est inconnue, pour que la durée de réponse ne trahisse pas
# l'existence d'un compte.
DUMMY_HASH = hash_password(secrets.token_urlsafe())


def hash_token(raw: str) -> str:
    """Les jetons ont 256 bits d'aléa : un SHA-256 simple suffit, pas besoin de sel."""
    return hashlib.sha256(raw.encode()).hexdigest()


def new_token() -> tuple[str, str]:
    """Renvoie (jeton à transmettre, condensat à stocker)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)
