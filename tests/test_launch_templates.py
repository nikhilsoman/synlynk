from synlynk import LAUNCH_TASK_TEMPLATES
from synlynk.hud import CYCLES


def test_every_template_cycle_is_a_governs_key():
    bad = [(t["id"], t["cycle"]) for t in LAUNCH_TASK_TEMPLATES if t["cycle"] not in CYCLES]
    assert bad == []


def test_specific_template_remaps():
    by_id = {t["id"]: t["cycle"] for t in LAUNCH_TASK_TEMPLATES}
    assert by_id["arch-review"] == "visualize"
    assert by_id["product-assessment"] == "goal"
    assert by_id["lifecycle-setup"] == "open"
    assert by_id["docs-audit"] == "notify"
    assert by_id["a11y-audit"] == "release"
    assert by_id["reduce-complexity"] == "execute"
    assert by_id["fix-churn-debt"] == "sustain"
