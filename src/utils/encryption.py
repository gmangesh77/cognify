"""Fernet-based encryption for API keys stored at rest."""

import os

import structlog
from cryptography.fernet import Fernet, InvalidToken

logger = structlog.get_logger()

_cached_key: bytes | None = None


class InvalidEncryptionKey(Exception):
    """Raised when decryption fails due to a wrong master key."""


def get_encryption_key() -> bytes:
    """Return the Fernet master key from env.

    In debug/test mode (COGNIFY_DEBUG=true), auto-generates an ephemeral
    key if unset. In production, raises ValueError to prevent data loss.
    """
    global _cached_key
    if _cached_key is not None:
        return _cached_key

    raw = os.environ.get("COGNIFY_ENCRYPTION_KEY", "")
    if raw:
        key = raw.encode()
        Fernet(key)  # validate it's a proper Fernet key
        _cached_key = key
        return _cached_key

    debug = os.environ.get("COGNIFY_DEBUG", "").lower() in ("true", "1")
    if not debug:
        raise ValueError(
            "COGNIFY_ENCRYPTION_KEY must be set in production. Generate with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )

    logger.warning(
        "encryption_key_auto_generated",
        msg="No COGNIFY_ENCRYPTION_KEY set — generating ephemeral key. "
        "Keys encrypted now will be unrecoverable after restart.",
    )
    _cached_key = Fernet.generate_key()
    return _cached_key


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string, returning a Fernet token."""
    f = Fernet(get_encryption_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    f = Fernet(get_encryption_key())
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise InvalidEncryptionKey(
            "Decryption failed — wrong encryption key or corrupted data"
        ) from exc
