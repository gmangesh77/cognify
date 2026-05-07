"""SSRF-guarded HTTP fetcher for editor-supplied image URLs.

Used by the upcoming `/api/v1/visuals/fetch-from-url` endpoint. Mirrors
impactai's `safe_http_url.py` pattern, hardened for image fetches:

1. Scheme allowlist (`http`, `https` only; reject userinfo).
2. Hostname pre-resolution via `socket.getaddrinfo`; reject any address
   that falls in private, loopback, link-local, CGNAT, multicast, or
   reserved CIDR ranges (IPv4 + IPv6).
3. HEAD probe for `Content-Length` and `Content-Type`. Validates size
   and MIME before committing to a body fetch.
4. Streamed GET with size enforced as bytes accumulate. Body MIME is
   re-validated via magic-byte sniff (Content-Type alone is untrusted).
5. Redirects validated on every hop. No retries.

All log entries use structlog and never include response bodies.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class FetchedImage:
    """Successfully fetched, validated image. Bytes are in-memory; caller persists."""

    url: str  # final URL after redirect chain
    bytes: bytes
    mime_type: str
    size_bytes: int


class SafeHttpError(Exception):
    """Base class for all SSRF / fetch failures."""


class SchemeRejected(SafeHttpError):
    """URL scheme is not in {http, https} or contains userinfo."""


class HostBlocked(SafeHttpError):
    """Resolved address falls in a blocked CIDR range."""


class MimeRejected(SafeHttpError):
    """Content-Type or sniffed MIME is not in the allowlist."""


class SizeExceeded(SafeHttpError):
    """Body length exceeds `max_size_bytes`."""


class FetchFailed(SafeHttpError):
    """Network error, timeout, non-2xx, or redirect-chain limit."""


_ALLOWED_SCHEMES = frozenset({"http", "https"})

# IPv4 ranges blocked beyond what `ipaddress.is_private` catches by default.
_BLOCKED_IPV4_NETS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)
_BLOCKED_IPV6_NETS = (
    ipaddress.ip_network("64:ff9b::/96"),  # NAT64
    ipaddress.ip_network("100::/64"),
    ipaddress.ip_network("2001::/32"),  # Teredo
    ipaddress.ip_network("2001:db8::/32"),  # docs
)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_WEBP_PREFIX = b"RIFF"
_WEBP_FORMAT = b"WEBP"


def _check_address_class(addr_str: str) -> None:
    """Raise HostBlocked if `addr_str` falls in any blocked CIDR class."""
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError as exc:
        raise HostBlocked(f"could not parse address {addr_str}: {exc}") from exc
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        raise HostBlocked(f"address {addr_str} is in a private/reserved CIDR class")
    extra_blocks = _BLOCKED_IPV4_NETS if addr.version == 4 else _BLOCKED_IPV6_NETS
    for net in extra_blocks:
        if addr in net:
            raise HostBlocked(f"address {addr_str} is in blocked range {net}")
    if addr.version == 6 and addr.ipv4_mapped is not None:
        _check_address_class(str(addr.ipv4_mapped))


def _resolve_and_validate_host(host: str) -> list[str]:
    """Resolve `host` via getaddrinfo and reject if any result is in a blocked class."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise FetchFailed(f"could not resolve host {host}: {exc}") from exc
    addresses = sorted({info[4][0] for info in infos if isinstance(info[4][0], str)})
    if not addresses:
        raise FetchFailed(f"host {host} resolved to no addresses")
    for addr_str in addresses:
        _check_address_class(addr_str)
    return addresses


def _validate_url(url: str) -> str:
    """Validate scheme and reject userinfo. Returns the URL with fragment stripped."""
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise SchemeRejected(
            f"scheme {parsed.scheme!r} not in {sorted(_ALLOWED_SCHEMES)}"
        )
    if "@" in (parsed.netloc or ""):
        raise SchemeRejected("userinfo in URL authority is not permitted")
    if not parsed.hostname:
        raise SchemeRejected("URL has no hostname")
    # Strip fragment.
    cleaned: str = parsed._replace(fragment="").geturl()
    return cleaned


def _sniff_mime(data: bytes) -> str | None:
    """Return the MIME type implied by magic bytes, or None if unrecognised."""
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == _WEBP_PREFIX and data[8:12] == _WEBP_FORMAT:
        return "image/webp"
    return None


class SafeHttpFetcher:
    """SSRF-guarded HTTP image fetcher.

    Constructed once per request scope (e.g. one per FastAPI route call) so
    settings can be applied freshly. Internally uses an `httpx.AsyncClient`
    that does NOT follow redirects automatically — we handle them manually
    so each hop can be re-validated.
    """

    def __init__(
        self,
        *,
        max_size_bytes: int,
        allowed_mime: list[str],
        timeout_s: float,
        max_redirects: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if max_size_bytes <= 0:
            raise ValueError("max_size_bytes must be > 0")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")
        if max_redirects < 0:
            raise ValueError("max_redirects must be >= 0")
        self._max_size = max_size_bytes
        self._allowed_mime = frozenset(allowed_mime)
        self._timeout = timeout_s
        self._max_redirects = max_redirects
        self._transport = transport

    async def fetch_image(self, url: str) -> FetchedImage:
        """Fetch and validate an image from `url`. Raises `SafeHttpError` on failure."""
        normalized = _validate_url(url)
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
            follow_redirects=False,
        ) as client:
            return await self._walk_and_fetch(client, normalized)

    async def _walk_and_fetch(
        self, client: httpx.AsyncClient, url: str
    ) -> FetchedImage:
        current = url
        for _ in range(self._max_redirects + 1):
            host = urlsplit(current).hostname
            if host is None:
                raise SchemeRejected("URL has no hostname")
            _resolve_and_validate_host(host)
            try:
                response = await client.head(current)
            except httpx.TimeoutException as exc:
                raise FetchFailed(f"HEAD timeout for {current}") from exc
            except httpx.HTTPError as exc:
                raise FetchFailed(f"HEAD network error for {current}: {exc}") from exc
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise FetchFailed(f"redirect from {current} has no Location")
                current = str(httpx.URL(current).join(location))
                continue
            self._enforce_head_size(response)
            advertised_mime = self._enforce_head_mime_optional(response)
            return await self._stream_get(client, current, advertised_mime)
        raise FetchFailed(f"redirect chain exceeded {self._max_redirects} hops")

    def _enforce_head_size(self, response: httpx.Response) -> None:
        cl = response.headers.get("content-length")
        if cl is None:
            return
        try:
            size = int(cl)
        except ValueError as exc:
            raise FetchFailed(f"invalid content-length: {cl!r}") from exc
        if size > self._max_size:
            raise SizeExceeded(f"advertised size {size} exceeds cap {self._max_size}")

    def _enforce_head_mime_optional(self, response: httpx.Response) -> str | None:
        ct = response.headers.get("content-type")
        if not ct:
            return None
        mime: str = ct.split(";", 1)[0].strip().lower()
        if mime and mime not in self._allowed_mime:
            raise MimeRejected(f"Content-Type {mime!r} not allowed")
        return mime

    async def _stream_get(
        self,
        client: httpx.AsyncClient,
        url: str,
        advertised_mime: str | None,
    ) -> FetchedImage:
        try:
            async with client.stream("GET", url) as response:
                if response.status_code >= 300:
                    raise FetchFailed(
                        f"GET {url} returned status {response.status_code}"
                    )
                buf = bytearray()
                async for chunk in response.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > self._max_size:
                        raise SizeExceeded(
                            f"streamed body exceeds {self._max_size} bytes"
                        )
                data = bytes(buf)
        except httpx.TimeoutException as exc:
            raise FetchFailed(f"GET timeout for {url}") from exc
        except httpx.HTTPError as exc:
            if isinstance(exc, SafeHttpError):  # pragma: no cover - defensive
                raise
            raise FetchFailed(f"GET network error for {url}: {exc}") from exc
        sniffed = _sniff_mime(data)
        if sniffed is None or sniffed not in self._allowed_mime:
            logger.info(
                "ssrf_rejected",
                reason="mime_sniff_mismatch",
                url=url,
                advertised=advertised_mime,
                sniffed=sniffed,
            )
            raise MimeRejected(
                f"sniffed MIME {sniffed!r} not in allowlist "
                f"(advertised {advertised_mime!r})"
            )
        return FetchedImage(
            url=url, bytes=data, mime_type=sniffed, size_bytes=len(data)
        )


__all__ = [
    "FetchFailed",
    "FetchedImage",
    "HostBlocked",
    "MimeRejected",
    "SafeHttpError",
    "SafeHttpFetcher",
    "SchemeRejected",
    "SizeExceeded",
]


# Re-exported for tests; private helper.
async def _await_briefly() -> None:  # pragma: no cover - schema-only helper
    await asyncio.sleep(0)
