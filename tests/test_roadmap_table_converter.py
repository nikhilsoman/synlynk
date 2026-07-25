from scripts.convert_roadmap_table import _parse_roadmap_version_arc_table


def test_parse_roadmap_version_arc_table_scopes_to_version_arc_section():
    content = """# synlynk Roadmap

## Version Arc

| Version | Theme | OS Layer | Status | Target |
| :--- | :--- | :--- | :--- | :--- |
| v0.1–v0.3.0 | Kernel + Filesystem | exec · telemetry · flatline · budget · project-docs ledger · enriched templates | ✅ Shipped | June 2026 |
| **v0.9.0** | **Kernel Fixes** | Scoped context · task→file mapping · verify contract · per-agent framing · Ed25519 wired · anti-gaming baseline (sample-count cap) | ✅ Shipped | June 2026 |
| ~~**v0.9.5**~~ | ~~Health Pulse~~ | Absorbed into v0.9.8 — all content (doctor, exit, repair, sync) landed in PR #70 | 📦 Retired → v0.9.8 | — |
| **v1.0.0** | **GA: Community Layer + Public Launch** | Workgroup protocol · signed capability ledger · SME archetype · game-resistant scoring · pipx/Homebrew PyPI · synlynk.com (BS-5) · Multi-repo workspace | 📋 Planned | Sep 2026 |

## Agent Archetype Model

| Archetype | Trigger | Examples |
| :--- | :--- | :--- |
| 🔧 Maintainers | Schedule · push · CI | Support Engineer ✅ · Security Guard · Compliance Officer |
"""

    rows = _parse_roadmap_version_arc_table(content)

    assert len(rows) == 4
    assert rows[0]["version"] == "v0.1–v0.3.0"
    assert rows[0]["title"] == "Kernel + Filesystem"
    assert rows[0]["status"] == "shipped"
    assert rows[0]["target_date"] == "June 2026"

    assert rows[1]["version"] == "v0.9.0"
    assert rows[1]["title"] == "Kernel Fixes"
    assert rows[1]["status"] == "shipped"

    assert rows[2]["version"] == "v0.9.5"
    assert rows[2]["title"] == "Health Pulse"
    assert rows[2]["status"] == "planned"
    assert rows[2]["target_date"] == "—"

    assert rows[3]["version"] == "v1.0.0"
    assert rows[3]["title"] == "GA: Community Layer + Public Launch"
    assert rows[3]["status"] == "planned"
    assert rows[3]["target_date"] == "Sep 2026"
