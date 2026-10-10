#!/usr/bin/env python3
"""
AI Voice Studio — Phase 5B-2 LAN Operational Preflight Script (Fail-Closed)

Validates network parameters, host interface binding, mDNS/DNS resolution,
Caddy Root CA presence, and tests configuration adaptation via Caddy v2.11.7
WITHOUT binding to any LAN socket.
"""

import argparse
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


def get_local_ipv4_addresses() -> set[str]:
    """Retrieves all non-loopback IPv4 addresses assigned to the local host."""
    ips = set()
    try:
        # Use PowerShell on Windows for authoritative interface inventory
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "@(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty IPAddress) -join ','"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        for ip in res.stdout.strip().split(","):
            ip = ip.strip()
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        # Fallback to socket interface enumeration
        try:
            hostname = socket.gethostname()
            for addr_info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = addr_info[4][0]
                if not ip.startswith("127."):
                    ips.add(ip)
        except Exception:
            pass
    return ips


def verify_mdns_resolution(hostname: str, target_ip: str) -> bool:
    """Verifies that the hostname resolves to target_ip (especially for .local mDNS)."""
    try:
        # PowerShell Resolve-DnsName supports mDNS natively on Windows 10/11
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f"@(Resolve-DnsName '{hostname}' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty IPAddress) -join ','"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        resolved_ips = [ip.strip() for ip in res.stdout.strip().split(",") if ip.strip()]
        if target_ip in resolved_ips:
            return True
    except Exception:
        pass

    try:
        # Python standard library fallback
        addrs = socket.getaddrinfo(hostname, None, socket.AF_INET)
        for a in addrs:
            if a[4][0] == target_ip:
                return True
    except Exception:
        pass

    return False


def validate_parameters(
    lan_ip: str,
    lan_hostname: str,
    approved_subnet: str,
    lan_port: int,
    caddy_root_ca: Path,
) -> tuple[bool, list[str]]:
    """Strict fail-closed parameter validation."""
    errors = []

    # 1. Reject placeholder addresses
    placeholders = {"192.168.1.50", "studio-server.local", "studio.local", "example.com"}
    host_ips = get_local_ipv4_addresses()

    # 2. LAN IP validation
    if not lan_ip:
        errors.append("LAN_IP is missing or empty.")
    else:
        try:
            ip_obj = ipaddress.IPv4Address(lan_ip)
            if ip_obj.is_loopback:
                errors.append(f"LAN_IP '{lan_ip}' is a loopback address. Must be a physical/LAN interface.")
            if ip_obj.is_unspecified:
                errors.append(f"LAN_IP '{lan_ip}' is a wildcard (0.0.0.0), which violates zero-exposure rules.")
            if ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_link_local:
                errors.append(f"LAN_IP '{lan_ip}' is invalid (multicast, reserved, or link-local APIPA).")

            if lan_ip not in host_ips:
                errors.append(
                    f"LAN_IP '{lan_ip}' does NOT belong to any active host network interface! "
                    f"Active non-loopback host IPs detected: {sorted(list(host_ips))}"
                )
        except ipaddress.AddressValueError:
            errors.append(f"LAN_IP '{lan_ip}' is not a valid IPv4 address.")

    # 3. Subnet validation (Fail-closed: prefix >= 24)
    if not approved_subnet:
        errors.append("STUDIO_APPROVED_SUBNET is missing or empty.")
    else:
        try:
            net_obj = ipaddress.IPv4Network(approved_subnet, strict=False)
            if net_obj.prefixlen < 24:
                errors.append(
                    f"STUDIO_APPROVED_SUBNET '{approved_subnet}' prefix /{net_obj.prefixlen} is overly broad! "
                    "Must be restricted to studio-specific subnet (/24 to /32)."
                )
            if lan_ip and errors == []:
                if ipaddress.IPv4Address(lan_ip) not in net_obj:
                    errors.append(
                        f"LAN_IP '{lan_ip}' is outside the approved subnet '{approved_subnet}'."
                    )
        except ipaddress.NetmaskValueError:
            errors.append(f"STUDIO_APPROVED_SUBNET '{approved_subnet}' is invalid.")

    # 4. Hostname validation
    if not lan_hostname:
        errors.append("LAN_HOSTNAME is missing or empty.")
    else:
        if not re.match(r"^[a-zA-Z0-9.-]+$", lan_hostname):
            errors.append(f"LAN_HOSTNAME '{lan_hostname}' contains invalid characters.")
        if lan_hostname.lower() in placeholders and lan_hostname.lower() not in [socket.gethostname().lower(), f"{socket.gethostname().lower()}.local"]:
            errors.append(
                f"LAN_HOSTNAME '{lan_hostname}' appears to be an unvalidated example placeholder."
            )

        if lan_hostname.lower().endswith(".local") and lan_ip:
            if not verify_mdns_resolution(lan_hostname, lan_ip):
                errors.append(
                    f"mDNS hostname '{lan_hostname}' failed to resolve to LAN_IP '{lan_ip}'. "
                    "Ensure Windows mDNS service is broadcasting or register hostname in local DNS/hosts."
                )

    # 5. Port validation
    if not (1024 <= lan_port <= 65535):
        errors.append(f"LAN_PORT '{lan_port}' must be an unprivileged port (1024-65535).")

    # 6. Caddy Root CA validation
    if not caddy_root_ca.exists():
        errors.append(f"Caddy Root CA file not found at: {caddy_root_ca}")
    else:
        ca_size = caddy_root_ca.stat().st_size
        if ca_size < 100:
            errors.append(f"Caddy Root CA file at {caddy_root_ca} is empty or corrupted ({ca_size} bytes).")

    return (len(errors) == 0, errors)


def extract_upstreams(obj) -> list[str]:
    """Recursively extracts all reverse_proxy upstream dial targets from adapted Caddy JSON."""
    dials = []
    if isinstance(obj, dict):
        if obj.get("handler") == "reverse_proxy":
            for u in obj.get("upstreams", []):
                if isinstance(u, dict) and "dial" in u:
                    dials.append(u["dial"])
        for v in obj.values():
            dials.extend(extract_upstreams(v))
    elif isinstance(obj, list):
        for item in obj:
            dials.extend(extract_upstreams(item))
    return dials


def run_caddy_validation_and_adapt(
    caddy_exe: Path,
    template_path: Path,
    lan_ip: str,
    lan_hostname: str,
    approved_subnet: str,
    lan_port: int,
    backend_port: int = 8769,
    is_pilot: bool = False,
) -> tuple[bool, str, dict]:
    """Generates a temporary Caddyfile and verifies syntax and JSON adaptation."""
    if not caddy_exe.exists():
        return False, f"Caddy executable not found at: {caddy_exe}", {}
    if not template_path.exists():
        return False, f"Caddyfile template not found at: {template_path}", {}

    template_content = template_path.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as td:
        temp_caddyfile = Path(td) / "Caddyfile.test"
        temp_caddyfile.write_text(template_content, encoding="utf-8")

        env = os.environ.copy()
        env["LAN_IP"] = lan_ip
        env["LAN_HOSTNAME"] = lan_hostname
        env["STUDIO_APPROVED_SUBNET"] = approved_subnet
        env["LAN_PORT"] = str(lan_port)
        env["BACKEND_PORT"] = str(backend_port)

        # 1. caddy validate
        val_res = subprocess.run(
            [str(caddy_exe), "validate", "--config", str(temp_caddyfile)],
            env=env,
            capture_output=True,
            text=True,
        )
        if val_res.returncode != 0:
            return False, f"caddy validate failed (code {val_res.returncode}):\n{val_res.stderr}\n{val_res.stdout}", {}

        # 2. caddy adapt
        adapt_res = subprocess.run(
            [str(caddy_exe), "adapt", "--config", str(temp_caddyfile)],
            env=env,
            capture_output=True,
            text=True,
        )
        if adapt_res.returncode != 0:
            return False, f"caddy adapt failed (code {adapt_res.returncode}):\n{adapt_res.stderr}\n{adapt_res.stdout}", {}

        try:
            adapted_json = json.loads(adapt_res.stdout)
        except json.JSONDecodeError as e:
            return False, f"Failed to parse adapted JSON: {e}\nOutput was: {adapt_res.stdout}", {}

        # 3. Security assertions on adapted JSON
        http_servers = adapted_json.get("apps", {}).get("http", {}).get("servers", {})
        for srv_name, srv_conf in http_servers.items():
            listen_list = srv_conf.get("listen", [])
            for listener in listen_list:
                if "0.0.0.0" in listener or listener.startswith(":"):
                    return False, f"Security Violation: Wildcard listener found in adapted configuration: {listener}", {}
                if listener == f"http://{lan_ip}:{lan_port}" or ":80" in listener:
                    return False, f"Security Violation: Plaintext HTTP listener found: {listener}", {}

        # 4. Upstream isolation assertions
        upstreams = extract_upstreams(adapted_json)
        if is_pilot or "pilot" in template_path.name.lower():
            if not upstreams:
                return False, "Security Violation: No reverse proxy upstreams found in adapted Pilot configuration.", {}

            # Security Invariant: Pilot Gateway must proxy EXCLUSIVELY to Sandbox 127.0.0.1:8769.
            # Regardless of any caller-supplied backend_port, 127.0.0.1:8769 is the ONLY permitted upstream.
            REQUIRED_SANDBOX_UPSTREAM = "127.0.0.1:8769"

            # Check 4A: Strict prohibition against Production API (port 8765)
            for u in upstreams:
                if "8765" in u:
                    return False, f"Security Violation: Upstream targets Production API (127.0.0.1:8765)! Detected: '{u}'. Pilot Gateway is strictly prohibited from proxying to Production.", {}

            # Check 4B: Strict prohibition against multiple/split upstreams
            unique_upstreams = set(upstreams)
            if len(unique_upstreams) > 1:
                return False, f"Security Violation: Multiple or split upstreams detected in Pilot Gateway: {sorted(list(unique_upstreams))}. Only single upstream 127.0.0.1:8769 is permitted.", {}

            # Check 4C: Strict match with Sandbox upstream
            for u in upstreams:
                if u != REQUIRED_SANDBOX_UPSTREAM:
                    return False, f"Security Violation: Upstream '{u}' is outside Sandbox. Pilot Gateway must proxy exclusively to Sandbox (127.0.0.1:8769).", {}

        return True, f"Caddy validate and adapt succeeded. Upstreams verified: {sorted(list(set(upstreams)))}", adapted_json


def main():
    parser = argparse.ArgumentParser(description="AI Voice Studio — Phase 5B-2 LAN Operational Preflight Check")
    parser.add_argument("--lan-ip", default=os.environ.get("LAN_IP", ""), help="Target static LAN IP of workstation")
    parser.add_argument("--lan-hostname", default=os.environ.get("LAN_HOSTNAME", ""), help="Target LAN hostname")
    parser.add_argument("--subnet", default=os.environ.get("STUDIO_APPROVED_SUBNET", ""), help="Approved studio subnet CIDR")
    parser.add_argument("--lan-port", type=int, default=int(os.environ.get("LAN_PORT", "9443")), help="HTTPS Gateway Port")
    parser.add_argument("--backend-port", type=int, default=int(os.environ.get("BACKEND_PORT", "8769")), help="Sandbox/Backend Port (Default 8769 for Pilot)")
    parser.add_argument("--root-ca", default="", help="Path to Caddy Root CA certificate")
    parser.add_argument("--caddy-exe", default="infra/caddy/caddy.exe", help="Path to Caddy executable")
    parser.add_argument("--template", default="infra/caddy/Caddyfile.pilot.template", help="Path to Caddyfile template")
    parser.add_argument("--pilot", action="store_true", default=True, help="Enforce pilot sandbox upstream isolation (127.0.0.1:8769)")

    args = parser.parse_args()

    appdata = os.environ.get("APPDATA", "")
    default_root_ca = Path(appdata) / "caddy" / "pki" / "authorities" / "local" / "root.crt" if appdata else Path("root.crt")
    root_ca_path = Path(args.root_ca) if args.root_ca else default_root_ca

    print("=" * 70)
    print("AI VOICE STUDIO — PHASE 5B-2 OPERATIONAL PREFLIGHT CHECK (FAIL-CLOSED)")
    print("=" * 70)
    print(f"Target LAN IP        : {args.lan_ip or '(NOT SET)'}")
    print(f"Target LAN Hostname  : {args.lan_hostname or '(NOT SET)'}")
    print(f"Approved Subnet      : {args.subnet or '(NOT SET)'}")
    print(f"Gateway HTTPS Port   : {args.lan_port}")
    print(f"Backend Port         : {args.backend_port}")
    print(f"Root CA Path         : {root_ca_path}")
    print("-" * 70)

    # 1. Validate parameters
    valid_params, errors = validate_parameters(
        lan_ip=args.lan_ip,
        lan_hostname=args.lan_hostname,
        approved_subnet=args.subnet,
        lan_port=args.lan_port,
        caddy_root_ca=root_ca_path,
    )

    if not valid_params:
        print("[-] PREFLIGHT PARAMETER VALIDATION FAILED:")
        for err in errors:
            print(f"    * {err}")
        print("\n[!] VERDICT: FAIL-CLOSED REJECTION — Deployment MUST NOT proceed.")
        sys.exit(1)

    print("[+] All network parameters, host interface binding, and Root CA validated.")

    # 2. Validate and adapt Caddy configuration in isolated temp sandbox
    caddy_ok, caddy_msg, _ = run_caddy_validation_and_adapt(
        caddy_exe=Path(args.caddy_exe).resolve(),
        template_path=Path(args.template).resolve(),
        lan_ip=args.lan_ip,
        lan_hostname=args.lan_hostname,
        approved_subnet=args.subnet,
        lan_port=args.lan_port,
        backend_port=args.backend_port,
        is_pilot=args.pilot,
    )

    if not caddy_ok:
        print(f"[-] CADDY CONFIGURATION ADAPTATION FAILED:\n    {caddy_msg}")
        print("\n[!] VERDICT: FAIL-CLOSED REJECTION — Caddy configuration is unsafe or invalid.")
        sys.exit(1)

    print(f"[+] {caddy_msg}")
    print("[+] Preflight check verified zero socket exposure and strict subnet ACL.")
    print("\n[+] FINAL PREFLIGHT VERDICT: READY FOR CONTROLLED GATE A AUTHORIZATION.")
    sys.exit(0)


if __name__ == "__main__":
    main()
