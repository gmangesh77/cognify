"""Tests for SafeHttpFetcher.

Uses `httpx.MockTransport` (no `respx` available) and patches
`socket.getaddrinfo` to control resolved addresses for SSRF tests.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import httpx
import pytest

from src.services.visuals.safe_http import (
    FetchFailed,
    HostBlocked,
    MimeRejected,
    SafeHttpFetcher,
    SchemeRejected,
    SizeExceeded,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_MAGIC = b"\xff\xd8\xff" + b"\x00" * 32
WEBP_MAGIC = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 32


def _patch_resolution(
    monkeypatch: pytest.MonkeyPatch, addresses: Iterable[str]
) -> None:
    """Force socket.getaddrinfo to return `addresses` regardless of host."""
    addr_list = list(addresses)

    def fake_getaddrinfo(
        host: str,
        _port: object,
        *_args: object,
        **_kwargs: object,
    ) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        return [(0, 0, 0, "", (a, 0)) for a in addr_list]

    monkeypatch.setattr(
        "src.services.visuals.safe_http.socket.getaddrinfo", fake_getaddrinfo
    )


def _make_fetcher(
    handler: Callable[[httpx.Request], httpx.Response],
) -> SafeHttpFetcher:
    transport = httpx.MockTransport(handler)
    return SafeHttpFetcher(
        max_size_bytes=10 * 1024 * 1024,
        allowed_mime=["image/png", "image/jpeg", "image/webp"],
        timeout_s=5.0,
        max_redirects=3,
        transport=transport,
    )


def _png_handler() -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={
                    "content-type": "image/png",
                    "content-length": str(len(PNG_MAGIC)),
                },
            )
        return httpx.Response(
            200,
            content=PNG_MAGIC,
            headers={"content-type": "image/png"},
        )

    return handler


@pytest.mark.asyncio
async def test_happy_path_png(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, ["104.21.62.118"])
    fetcher = _make_fetcher(_png_handler())
    result = await fetcher.fetch_image("https://example.com/img.png")
    assert result.mime_type == "image/png"
    assert result.bytes == PNG_MAGIC
    assert result.size_bytes == len(PNG_MAGIC)


@pytest.mark.asyncio
async def test_happy_path_jpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, ["104.21.62.118"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={
                    "content-type": "image/jpeg",
                    "content-length": str(len(JPEG_MAGIC)),
                },
            )
        return httpx.Response(
            200, content=JPEG_MAGIC, headers={"content-type": "image/jpeg"}
        )

    fetcher = _make_fetcher(handler)
    result = await fetcher.fetch_image("https://example.com/photo.jpg")
    assert result.mime_type == "image/jpeg"


@pytest.mark.asyncio
async def test_happy_path_webp(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, ["104.21.62.118"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={
                    "content-type": "image/webp",
                    "content-length": str(len(WEBP_MAGIC)),
                },
            )
        return httpx.Response(
            200, content=WEBP_MAGIC, headers={"content-type": "image/webp"}
        )

    fetcher = _make_fetcher(handler)
    result = await fetcher.fetch_image("https://example.com/img.webp")
    assert result.mime_type == "image/webp"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/img.png",
        "file:///etc/passwd",
        "data:image/png;base64,xxx",
        "javascript:alert(1)",
        "gopher://example.com/img",
    ],
)
async def test_scheme_rejected(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, ["104.21.62.118"])
    fetcher = _make_fetcher(_png_handler())
    with pytest.raises(SchemeRejected):
        await fetcher.fetch_image(url)


@pytest.mark.asyncio
async def test_userinfo_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, ["104.21.62.118"])
    fetcher = _make_fetcher(_png_handler())
    with pytest.raises(SchemeRejected):
        await fetcher.fetch_image("https://user:pass@example.com/img.png")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "addr",
    [
        "127.0.0.1",  # loopback
        "10.0.0.1",  # private
        "192.168.1.1",  # private
        "172.16.0.5",  # private
        "169.254.169.254",  # link-local (AWS metadata)
        "100.64.0.1",  # CGNAT
        "0.0.0.0",  # unspecified
        "224.0.0.1",  # multicast
        "240.0.0.1",  # reserved
    ],
)
async def test_blocked_ipv4(addr: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, [addr])
    fetcher = _make_fetcher(_png_handler())
    with pytest.raises(HostBlocked):
        await fetcher.fetch_image("http://example.com/img.png")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "addr",
    [
        "::1",  # loopback
        "fc00::1",  # ULA
        "fe80::1",  # link-local
        "ff00::1",  # multicast
    ],
)
async def test_blocked_ipv6(addr: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, [addr])
    fetcher = _make_fetcher(_png_handler())
    with pytest.raises(HostBlocked):
        await fetcher.fetch_image("http://example.com/img.png")


@pytest.mark.asyncio
async def test_redirect_to_private_ip_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First hop resolves public; second hop resolves loopback."""
    addr_iter = iter(
        [
            ["104.21.62.118"],  # first HEAD -> public
            ["127.0.0.1"],  # second HEAD after redirect -> blocked
        ]
    )

    def fake_getaddrinfo(
        *_a: object, **_kw: object
    ) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        addresses = next(addr_iter)
        return [(0, 0, 0, "", (a, 0)) for a in addresses]

    monkeypatch.setattr(
        "src.services.visuals.safe_http.socket.getaddrinfo", fake_getaddrinfo
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "internal" in str(request.url):
            return httpx.Response(
                200, content=PNG_MAGIC, headers={"content-type": "image/png"}
            )
        return httpx.Response(
            302, headers={"location": "http://internal.example.com/img.png"}
        )

    fetcher = _make_fetcher(handler)
    with pytest.raises(HostBlocked):
        await fetcher.fetch_image("https://example.com/img.png")


@pytest.mark.asyncio
async def test_redirect_chain_over_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, ["104.21.62.118"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://example.com/next"})

    fetcher = _make_fetcher(handler)
    with pytest.raises(FetchFailed):
        await fetcher.fetch_image("https://example.com/img.png")


@pytest.mark.asyncio
async def test_head_advertises_oversize(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, ["104.21.62.118"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={
                    "content-type": "image/png",
                    "content-length": str(20 * 1024 * 1024),
                },
            )
        return httpx.Response(
            200, content=PNG_MAGIC, headers={"content-type": "image/png"}
        )

    fetcher = _make_fetcher(handler)
    with pytest.raises(SizeExceeded):
        await fetcher.fetch_image("https://example.com/img.png")


@pytest.mark.asyncio
async def test_streamed_body_exceeds_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, ["104.21.62.118"])

    big = b"\x89PNG" + b"\x00" * (11 * 1024 * 1024)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-type": "image/png"})
        return httpx.Response(200, content=big, headers={"content-type": "image/png"})

    fetcher = _make_fetcher(handler)
    with pytest.raises(SizeExceeded):
        await fetcher.fetch_image("https://example.com/img.png")


@pytest.mark.asyncio
async def test_head_content_type_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, ["104.21.62.118"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"})

    fetcher = _make_fetcher(handler)
    with pytest.raises(MimeRejected):
        await fetcher.fetch_image("https://example.com/file.pdf")


@pytest.mark.asyncio
async def test_mime_spoofed_body_does_not_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Server claims image/png but body starts with HTML."""
    _patch_resolution(monkeypatch, ["104.21.62.118"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-type": "image/png"})
        return httpx.Response(
            200,
            content=b"<html><body>nope</body></html>",
            headers={"content-type": "image/png"},
        )

    fetcher = _make_fetcher(handler)
    with pytest.raises(MimeRejected):
        await fetcher.fetch_image("https://example.com/img.png")


@pytest.mark.asyncio
async def test_non_2xx_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resolution(monkeypatch, ["104.21.62.118"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-type": "image/png"})
        return httpx.Response(404)

    fetcher = _make_fetcher(handler)
    with pytest.raises(FetchFailed):
        await fetcher.fetch_image("https://example.com/img.png")


@pytest.mark.asyncio
async def test_dns_failure_yields_fetchfailed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(*_a: object, **_kw: object) -> list[object]:
        raise OSError("nodename nor servname provided")

    monkeypatch.setattr(
        "src.services.visuals.safe_http.socket.getaddrinfo", fake_getaddrinfo
    )
    fetcher = _make_fetcher(_png_handler())
    with pytest.raises(FetchFailed):
        await fetcher.fetch_image("https://example.com/img.png")


def test_constructor_validates_inputs() -> None:
    with pytest.raises(ValueError):
        SafeHttpFetcher(max_size_bytes=0, allowed_mime=["image/png"], timeout_s=1.0)
    with pytest.raises(ValueError):
        SafeHttpFetcher(max_size_bytes=10, allowed_mime=["image/png"], timeout_s=0)
    with pytest.raises(ValueError):
        SafeHttpFetcher(
            max_size_bytes=10,
            allowed_mime=["image/png"],
            timeout_s=1.0,
            max_redirects=-1,
        )
