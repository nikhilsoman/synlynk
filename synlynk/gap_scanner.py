from pathlib import Path
from typing import Dict, Any, List


def scan_workspace_gaps(discovery_data: Dict[str, Any], repo_root: str) -> List[Dict[str, Any]]:
    """Scan workspace for high-value, non-destructive first-win candidates."""
    p = Path(repo_root)
    gaps: List[Dict[str, Any]] = []

    # Check for unit test suites across standard language conventions
    tests = (
        list(p.glob("**/test_*.py"))
        + list(p.glob("**/*_test.go"))
        + list(p.glob("**/*.test.ts"))
        + list(p.glob("**/*.test.js"))
        + list(p.glob("**/*.spec.ts"))
        + list(p.glob("**/*.spec.js"))
    )
    if not tests:
        gaps.append({
            "type": "missing_unit_tests",
            "target": "core_modules",
            "desc": "No automated test suite detected in repository.",
        })

    # Check for health check route if routes are detected in discovery data
    routes = discovery_data.get("logical", {}).get("routes", [])
    if routes:
        paths = [r.get("path", "") for r in routes]
        if not any(hp in paths for hp in ("/health", "/healthz", "/ping", "/status")):
            gaps.append({
                "type": "missing_health_check",
                "target": "api_gateway",
                "desc": "No standard /health or /ping endpoint discovered in service routes.",
            })

    return gaps


def generate_governs_goal(gap: Dict[str, Any]) -> Dict[str, Any]:
    """Translate discovered gap into a strict GOVERNS goal specification."""
    gap_type = gap.get("type", "")
    target = gap.get("target", "core modules")

    if gap_type == "missing_unit_tests":
        outcome = f"Establish 100% test coverage and verification gate for {target}"
        criterion = "pytest runs in CI and passes with 100% green exit code"
    elif gap_type == "missing_health_check":
        outcome = f"Implement resilient /health probe and liveness check for {target}"
        criterion = "HTTP GET /health returns 200 OK with runtime status payload"
    else:
        outcome = f"Resolve discovered workspace gap in {target}"
        criterion = "Verification suite runs and passes cleanly without regressions"

    return {
        "outcome": outcome,
        "criterion": criterion,
        "command": f'synlynk goal create --outcome "{outcome}" --criterion "{criterion}"',
    }
