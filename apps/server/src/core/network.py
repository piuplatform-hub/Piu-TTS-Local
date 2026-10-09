"""
Network & Reverse Proxy Utilities
Handles secure client IP extraction behind trusted reverse proxies (e.g. Caddy).
Conforms to RFC 7239 and OWASP guidelines, preventing IP spoofing.
"""

import ipaddress
import logging
from typing import Optional, Set
from fastapi import Request

from ..config import settings

logger = logging.getLogger("studio.network")


def normalize_ip(raw: str) -> Optional[str]:
    """
    Normalizes and validates an IP string candidate.
    Handles:
    - Standard IPv4 ("192.168.1.1")
    - Standard IPv6 ("::1", "2001:db8::1")
    - Bracketed IPv6 with optional port ("[2001:db8::1]:8443" -> "2001:db8::1")
    - IPv4 with port ("192.168.1.1:8080" -> "192.168.1.1")
    - Strips whitespace.
    Returns canonical IP string or None if invalid/malformed.
    """
    if not raw or not isinstance(raw, str):
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    # Handle bracketed IPv6 (with or without port)
    if cleaned.startswith("["):
        if "]" in cleaned:
            end_bracket = cleaned.index("]")
            ip_candidate = cleaned[1:end_bracket]
            port_part = cleaned[end_bracket + 1 :]
            if port_part:
                if not port_part.startswith(":"):
                    return None
                port_str = port_part[1:]
                if not (port_str.isdigit() and 1 <= int(port_str) <= 65535):
                    return None
            try:
                ip_obj = ipaddress.ip_address(ip_candidate)
                if isinstance(ip_obj, ipaddress.IPv6Address):
                    return str(ip_obj)
            except ValueError:
                return None
        return None

    # Handle IPv4 with port (e.g. 192.168.1.50:54321)
    if ":" in cleaned and cleaned.count(":") == 1:
        ip_part, _, port_part = cleaned.partition(":")
        if not (port_part.isdigit() and 1 <= int(port_part) <= 65535):
            return None
        try:
            ip_obj = ipaddress.ip_address(ip_part)
            if isinstance(ip_obj, ipaddress.IPv4Address):
                return str(ip_obj)
        except ValueError:
            return None
        return None

    # Direct IP address parsing
    try:
        ip_obj = ipaddress.ip_address(cleaned)
        return str(ip_obj)
    except ValueError:
        return None


def extract_client_ip(request: Request) -> str:
    """
    Extracts the authenticated or true client IP address.

    Security Rules:
    1. Direct TCP socket peer IP (`request.client.host`) is the baseline.
    2. Forwarded headers (`X-Forwarded-For`, `X-Real-IP`) are ONLY inspected
       if the direct socket peer is explicitly listed in `settings.TRUSTED_PROXIES`
       AND `settings.TRUST_FORWARDED_HEADERS` is True.
    3. If the peer is NOT trusted, forwarded headers are completely IGNORED
       to prevent IP spoofing attacks.
    4. When traversing `X-Forwarded-For` from a trusted proxy, the chain is evaluated
       from right to left: the closest untrusted hop represents the true client.
    5. All candidate strings are strictly validated against `ipaddress.ip_address`.
    """
    peer_ip = "127.0.0.1"
    if request.client and request.client.host:
        normalized_peer = normalize_ip(request.client.host)
        peer_ip = normalized_peer or request.client.host

    # If forwarded headers are disabled or peer is not a trusted reverse proxy,
    # strictly return the immediate socket peer IP.
    trusted_set: Set[str] = set(settings.TRUSTED_PROXIES)
    if not settings.TRUST_FORWARDED_HEADERS or peer_ip not in trusted_set:
        return peer_ip

    # Inspect X-Forwarded-For
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
        # Traverse right-to-left
        fallback_candidate: Optional[str] = None
        for part in reversed(parts):
            norm = normalize_ip(part)
            if not norm:
                continue
            if norm not in trusted_set:
                return norm
            if fallback_candidate is None:
                fallback_candidate = norm

        if fallback_candidate:
            return fallback_candidate

    # Inspect X-Real-IP fallback
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        norm = normalize_ip(real_ip)
        if norm:
            return norm

    # Fallback to direct peer IP
    return peer_ip
