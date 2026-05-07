"""Tests for the shared SSRF/URL guards (INFRA-006)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.utils.safe_url import (
    UrlHostBlocked,
    UrlSchemeRejected,
    assert_address_class_safe,
    assert_outbound_url_safe,
    assert_url_scheme_safe,
)


class TestAssertUrlSchemeSafe:
    def test_accepts_http(self) -> None:
        assert assert_url_scheme_safe("http://example.com") == "http://example.com"

    def test_accepts_https(self) -> None:
        assert assert_url_scheme_safe("https://api.example.com/v2") == (
            "https://api.example.com/v2"
        )

    def test_strips_fragment(self) -> None:
        cleaned = assert_url_scheme_safe("https://example.com/page#frag")
        assert "#" not in cleaned

    def test_rejects_ftp(self) -> None:
        with pytest.raises(UrlSchemeRejected):
            assert_url_scheme_safe("ftp://example.com")

    def test_rejects_file(self) -> None:
        with pytest.raises(UrlSchemeRejected):
            assert_url_scheme_safe("file:///etc/passwd")

    def test_rejects_userinfo(self) -> None:
        with pytest.raises(UrlSchemeRejected):
            assert_url_scheme_safe("https://user:pass@example.com/")

    def test_rejects_no_hostname(self) -> None:
        with pytest.raises(UrlSchemeRejected):
            assert_url_scheme_safe("https:///path")


class TestAssertAddressClassSafe:
    @pytest.mark.parametrize(
        "addr",
        [
            "127.0.0.1",
            "192.168.1.5",
            "10.0.0.1",
            "172.16.0.1",
            "169.254.1.1",  # link-local
            "0.0.0.0",
            "100.64.0.1",  # CGNAT
            "::1",
        ],
    )
    def test_blocks_private_and_reserved(self, addr: str) -> None:
        with pytest.raises(UrlHostBlocked):
            assert_address_class_safe(addr)

    @pytest.mark.parametrize(
        "addr",
        ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"],
    )
    def test_allows_public(self, addr: str) -> None:
        assert_address_class_safe(addr)  # no raise

    def test_blocks_ipv4_mapped_in_ipv6(self) -> None:
        with pytest.raises(UrlHostBlocked):
            assert_address_class_safe("::ffff:127.0.0.1")


class TestAssertOutboundUrlSafe:
    def test_rejects_unsafe_scheme_without_dns(self) -> None:
        with pytest.raises(UrlSchemeRejected):
            assert_outbound_url_safe("ftp://example.com/x")

    def test_dns_resolution_to_public_ip_passes(self) -> None:
        with patch(
            "src.utils.safe_url.socket.getaddrinfo",
            return_value=[(0, 0, 0, "", ("8.8.8.8", 0))],
        ):
            assert (
                assert_outbound_url_safe("https://example.com/v2")
                == "https://example.com/v2"
            )

    def test_dns_resolution_to_private_ip_blocks(self) -> None:
        with (
            patch(
                "src.utils.safe_url.socket.getaddrinfo",
                return_value=[(0, 0, 0, "", ("192.168.1.5", 0))],
            ),
            pytest.raises(UrlHostBlocked),
        ):
            assert_outbound_url_safe("https://intranet.example.com/")
