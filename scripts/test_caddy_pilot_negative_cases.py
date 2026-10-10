#!/usr/bin/env python3
"""
AI Voice Studio — Phase 5B Gate A: Caddy Pilot Fail-Closed Negative Tests
Verifies that preflight fails closed on modified Caddyfiles pointing to:
1. Production API (127.0.0.1:8765)
2. Dual upstreams (127.0.0.1:8769 and 127.0.0.1:8765)
3. External upstream outside sandbox (e.g. 10.0.0.1:8080 or 127.0.0.1:9000)
Regardless of caller-supplied backend_port.
"""

import sys
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.lan_preflight_check import run_caddy_validation_and_adapt

CADDY_EXE = WORKSPACE_ROOT / "infra" / "caddy" / "caddy.exe"
BASE_TEMPLATE = WORKSPACE_ROOT / "infra" / "caddy" / "Caddyfile.pilot.template"


def run_negative_tests() -> dict:
    if not CADDY_EXE.exists():
        raise FileNotFoundError(f"Caddy executable not found: {CADDY_EXE}")
    if not BASE_TEMPLATE.exists():
        raise FileNotFoundError(f"Base template not found: {BASE_TEMPLATE}")

    base_content = BASE_TEMPLATE.read_text(encoding="utf-8")
    results = {}

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)

        # ----------------------------------------------------------------------
        # Case 0: Baseline unmodified pilot template (Should PASS)
        # ----------------------------------------------------------------------
        ok0, msg0, _ = run_caddy_validation_and_adapt(
            caddy_exe=CADDY_EXE,
            template_path=BASE_TEMPLATE,
            lan_ip="192.168.1.100",
            lan_hostname="studio-pilot.local",
            approved_subnet="192.168.1.0/24",
            lan_port=9443,
            backend_port=8769,
            is_pilot=True,
        )
        results["case_0_baseline_valid"] = {
            "passed": ok0,
            "message": msg0,
            "verdict": "EXPECTED_PASS" if ok0 else "UNEXPECTED_FAIL",
        }
        assert ok0, f"Baseline template failed: {msg0}"

        # ----------------------------------------------------------------------
        # Case 1: Upstream modified to Production API (127.0.0.1:8765)
        # ----------------------------------------------------------------------
        caddyfile_case1 = temp_dir / "Caddyfile.case1.prod"
        content_case1 = base_content.replace("127.0.0.1:8769", "127.0.0.1:8765")
        caddyfile_case1.write_text(content_case1, encoding="utf-8")

        # Test with caller asking for 8769
        ok1a, msg1a, _ = run_caddy_validation_and_adapt(
            caddy_exe=CADDY_EXE,
            template_path=caddyfile_case1,
            lan_ip="192.168.1.100",
            lan_hostname="studio-pilot.local",
            approved_subnet="192.168.1.0/24",
            lan_port=9443,
            backend_port=8769,
            is_pilot=True,
        )
        # Test with caller trying to trick validator by passing backend_port=8765
        ok1b, msg1b, _ = run_caddy_validation_and_adapt(
            caddy_exe=CADDY_EXE,
            template_path=caddyfile_case1,
            lan_ip="192.168.1.100",
            lan_hostname="studio-pilot.local",
            approved_subnet="192.168.1.0/24",
            lan_port=9443,
            backend_port=8765,
            is_pilot=True,
        )
        results["case_1_production_api_target"] = {
            "rejected_with_port_8769": not ok1a,
            "message_8769": msg1a,
            "rejected_with_tricked_port_8765": not ok1b,
            "message_8765": msg1b,
            "verdict": "FAIL_CLOSED_CONFIRMED" if (not ok1a and not ok1b) else "SECURITY_LEAK",
        }
        assert not ok1a and not ok1b, "Case 1 failed to reject production upstream!"

        # ----------------------------------------------------------------------
        # Case 2: Dual upstreams (127.0.0.1:8769 AND 127.0.0.1:8765)
        # ----------------------------------------------------------------------
        caddyfile_case2 = temp_dir / "Caddyfile.case2.dual"
        # In Caddy, reverse_proxy can have multiple upstreams: reverse_proxy 127.0.0.1:8769 127.0.0.1:8765
        content_case2 = base_content.replace(
            "reverse_proxy 127.0.0.1:8769 {",
            "reverse_proxy 127.0.0.1:8769 127.0.0.1:8765 {"
        )
        caddyfile_case2.write_text(content_case2, encoding="utf-8")

        ok2, msg2, _ = run_caddy_validation_and_adapt(
            caddy_exe=CADDY_EXE,
            template_path=caddyfile_case2,
            lan_ip="192.168.1.100",
            lan_hostname="studio-pilot.local",
            approved_subnet="192.168.1.0/24",
            lan_port=9443,
            backend_port=8769,
            is_pilot=True,
        )
        results["case_2_dual_split_upstreams"] = {
            "rejected": not ok2,
            "message": msg2,
            "verdict": "FAIL_CLOSED_CONFIRMED" if not ok2 else "SECURITY_LEAK",
        }
        assert not ok2, "Case 2 failed to reject dual upstreams!"

        # ----------------------------------------------------------------------
        # Case 3: External upstream outside sandbox (10.0.0.1:8080)
        # ----------------------------------------------------------------------
        caddyfile_case3 = temp_dir / "Caddyfile.case3.external"
        content_case3 = base_content.replace("127.0.0.1:8769", "10.0.0.1:8080")
        caddyfile_case3.write_text(content_case3, encoding="utf-8")

        ok3, msg3, _ = run_caddy_validation_and_adapt(
            caddy_exe=CADDY_EXE,
            template_path=caddyfile_case3,
            lan_ip="192.168.1.100",
            lan_hostname="studio-pilot.local",
            approved_subnet="192.168.1.0/24",
            lan_port=9443,
            backend_port=8769,
            is_pilot=True,
        )
        results["case_3_external_upstream_target"] = {
            "rejected": not ok3,
            "message": msg3,
            "verdict": "FAIL_CLOSED_CONFIRMED" if not ok3 else "SECURITY_LEAK",
        }
        assert not ok3, "Case 3 failed to reject external upstream!"

    return results


def main():
    print("=" * 70)
    print("AI VOICE STUDIO — CADDY PILOT FAIL-CLOSED NEGATIVE TESTS")
    print("=" * 70)

    res = run_negative_tests()

    print("[+] Case 0: Baseline Unmodified Template (127.0.0.1:8769)")
    print(f"    - Passed  : {res['case_0_baseline_valid']['passed']}")
    print(f"    - Message : {res['case_0_baseline_valid']['message']}")
    print(f"    - Verdict : {res['case_0_baseline_valid']['verdict']}\n")

    print("[+] Case 1: Modified Upstream -> Production API (127.0.0.1:8765)")
    print(f"    - Rejected with --backend-port 8769 : {res['case_1_production_api_target']['rejected_with_port_8769']}")
    print(f"      Message: {res['case_1_production_api_target']['message_8769']}")
    print(f"    - Rejected with --backend-port 8765 : {res['case_1_production_api_target']['rejected_with_tricked_port_8765']}")
    print(f"      Message: {res['case_1_production_api_target']['message_8765']}")
    print(f"    - Verdict : {res['case_1_production_api_target']['verdict']}\n")

    print("[+] Case 2: Modified Upstream -> Dual (127.0.0.1:8769 & 127.0.0.1:8765)")
    print(f"    - Rejected : {res['case_2_dual_split_upstreams']['rejected']}")
    print(f"      Message  : {res['case_2_dual_split_upstreams']['message']}")
    print(f"    - Verdict  : {res['case_2_dual_split_upstreams']['verdict']}\n")

    print("[+] Case 3: Modified Upstream -> External (10.0.0.1:8080)")
    print(f"    - Rejected : {res['case_3_external_upstream_target']['rejected']}")
    print(f"      Message  : {res['case_3_external_upstream_target']['message']}")
    print(f"    - Verdict  : {res['case_3_external_upstream_target']['verdict']}\n")

    print("=" * 70)
    print("[+] OVERALL VERDICT: ALL NEGATIVE CASES SUCCESSFULLY FAILED CLOSED.")
    print("    SECURITY INVARIANT ENFORCED: STRICTLY 127.0.0.1:8769 ONLY.")
    print("=" * 70)


if __name__ == "__main__":
    main()
