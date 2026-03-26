"""Tests for Fernet-based API key encryption utility."""

import os
from unittest.mock import patch

import pytest

from src.utils.encryption import (
    InvalidEncryptionKey,
    decrypt_value,
    encrypt_value,
    get_encryption_key,
)


@pytest.fixture(autouse=True)
def _clear_key_cache() -> None:
    """Reset the cached encryption key between tests."""
    import src.utils.encryption as mod
    mod._cached_key = None
    yield
    mod._cached_key = None


class TestGetEncryptionKey:
    def test_reads_from_env(self) -> None:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"COGNIFY_ENCRYPTION_KEY": key}):
            result = get_encryption_key()
        assert result == key.encode()

    def test_auto_generates_when_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("COGNIFY_ENCRYPTION_KEY", None)
            result = get_encryption_key()
        assert len(result) > 0
        # Should be a valid Fernet key
        from cryptography.fernet import Fernet

        Fernet(result)  # doesn't raise


class TestEncryptDecrypt:
    def test_roundtrip(self) -> None:
        plaintext = "sk-ant-api03-real-key-value-12345"
        ciphertext = encrypt_value(plaintext)
        assert decrypt_value(ciphertext) == plaintext

    def test_encrypt_returns_different_from_input(self) -> None:
        plaintext = "sk-ant-api03-real-key-value-12345"
        ciphertext = encrypt_value(plaintext)
        assert ciphertext != plaintext

    def test_encrypt_empty_string(self) -> None:
        ciphertext = encrypt_value("")
        assert decrypt_value(ciphertext) == ""

    def test_decrypt_wrong_key_raises(self) -> None:
        from cryptography.fernet import Fernet

        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        with patch.dict(os.environ, {"COGNIFY_ENCRYPTION_KEY": key1}):
            import src.utils.encryption as mod
            mod._cached_key = None
            ciphertext = encrypt_value("my-secret")

        with patch.dict(os.environ, {"COGNIFY_ENCRYPTION_KEY": key2}):
            mod._cached_key = None
            with pytest.raises(InvalidEncryptionKey):
                decrypt_value(ciphertext)

    def test_ciphertext_starts_with_fernet_prefix(self) -> None:
        ciphertext = encrypt_value("test-key")
        assert ciphertext.startswith("gAAAAA")
