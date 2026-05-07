"""Reusable SSRF guards for outbound URLs (INFRA-006).

Extracted from `src/services/visuals/safe_http.py` so trend sources
(arXiv, Hacker News, NewsAPI) and any future outbound caller can share
the same scheme + host-CIDR validation without pulling in the
image-fetch streaming machinery.

Two layers:

- `assert_url_scheme_safe(url)` — pure URL syntax checks. Returns the
  cleaned URL on success.
- `assert_outbound_host_safe(host)` — DNS-resolves `host` and rejects
  if any A/AAAA record falls in a private/loopback/link-local/CGNAT/
  reserved CIDR class. Performs blocking I/O (`socket.getaddrinfo`)
  and is intended for one-shot validation at config-load time.

`assert_outbound_url_safe(url)` runs both. Use this from any place
that consumes a configurable URL — trend-client constructors, future
webhook delivery, etc. The image-fetch path keeps using the richer
`SafeHttpFetcher` from `src/services/visuals/safe_http.py`, which
re-exports these primitives.

Errors derive from `OutboundUrlError` so callers can catch one base
class. The image-fetch path's own `SafeHttpError` continues to alias
the same hierarchy for backward compatibility.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class OutboundUrlError(Exception):
    """Base class for all outbound-URL safety failures."""


class UrlSchemeRejected(OutboundUrlError):
    """URL scheme is not in {http, https} or contains userinfo."""


class UrlHostBlocked(OutboundUrlError):
    """Resolved address falls in a blocked CIDR range."""


class UrlResolutionFailed(OutboundUrlError):
    """Hostname could not be resolved at all."""


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


def assert_url_scheme_safe(url: str) -> str:
    """Validate scheme + reject userinfo. Returns the URL with fragment stripped."""
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UrlSchemeRejected(
            f"scheme {parsed.scheme!r} not in {sorted(_ALLOWED_SCHEMES)}"
        )
    if "@" in (parsed.netloc or ""):
        raise UrlSchemeRejected("userinfo in URL authority is not permitted")
    if not parsed.hostname:
        raise UrlSchemeRejected("URL has no hostname")
    return parsed._replace(fragment="").geturl()


def assert_address_class_safe(addr_str: str) -> None:
    """Raise `UrlHostBlocked` if `addr_str` falls in any blocked CIDR class."""
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError as exc:
        raise UrlHostBlocked(f"could not parse address {addr_str}: {exc}") from exc
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        raise UrlHostBlocked(f"address {addr_str} is in a private/reserved CIDR class")
    extra_blocks = _BLOCKED_IPV4_NETS if addr.version == 4 else _BLOCKED_IPV6_NETS
    for net in extra_blocks:
        if addr in net:
            raise UrlHostBlocked(f"address {addr_str} is in blocked range {net}")
    if addr.version == 6 and addr.ipv4_mapped is not None:
        assert_address_class_safe(str(addr.ipv4_mapped))


def assert_outbound_host_safe(host: str) -> list[str]:
    """Resolve `host` and reject if any address is in a blocked CIDR class.

    Returns the resolved address list on success — useful for diagnostics
    + logging.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise UrlResolutionFailed(f"could not resolve host {host}: {exc}") from exc
    addresses = sorted({info[4][0] for info in infos if isinstance(info[4][0], str)})
    if not addresses:
        raise UrlResolutionFailed(f"host {host} resolved to no addresses")
    for addr_str in addresses:
        assert_address_class_safe(addr_str)
    return addresses


def assert_outbound_url_safe(url: str) -> str:
    """Run both scheme and host checks. Returns the cleaned URL on success.

    Use from any code that consumes a configurable URL (trend clients,
    webhook delivery, etc.). For editor-supplied image URLs use
    `SafeHttpFetcher` from `src/services/visuals/safe_http.py` instead —
    that path adds MIME sniffing, size enforcement, and per-redirect
    re-validation.
    """
    cleaned = assert_url_scheme_safe(url)
    host = urlsplit(cleaned).hostname
    if host is None:  # pragma: no cover — assert_url_scheme_safe already checks
        raise UrlSchemeRejected("URL has no hostname")
    assert_outbound_host_safe(host)
    return cleaned


__all__ = [
    "OutboundUrlError",
    "UrlHostBlocked",
    "UrlResolutionFailed",
    "UrlSchemeRejected",
    "assert_address_class_safe",
    "assert_outbound_host_safe",
    "assert_outbound_url_safe",
    "assert_url_scheme_safe",
]
