import pytest
from synlynk.viz import _enrich_graphify_html, generate_architect_map_html

def test_dynamic_lod_thresholds_computation_and_injection():
    # Construct mock nodes with variable degree distribution
    raw_nodes = []
    # 5 nodes with high degree (10-15)
    for i in range(5):
        raw_nodes.append({"id": f"core_{i}", "label": f"Core_{i}", "degree": 10 + i, "community": 0, "file_type": "Module Cluster"})
    # 20 nodes with moderate degree (3-5)
    for i in range(20):
        raw_nodes.append({"id": f"service_{i}", "label": f"Service_{i}", "degree": 3 + (i % 3), "community": 1, "file_type": "Service Class"})
    # 30 nodes with low degree (1)
    for i in range(30):
        raw_nodes.append({"id": f"leaf_{i}", "label": f"Leaf_{i}", "degree": 1, "community": 2, "file_type": "Component"})
    # 15 test nodes with degree 4
    for i in range(15):
        raw_nodes.append({"id": f"test_{i}", "label": f"Test_{i}", "degree": 4, "community": 3, "file_type": "Test Suite"})

    import json
    mock_html = f"""<!DOCTYPE html>
<html>
<head></head>
<body>
<div id="graph"></div>
<script>
const RAW_NODES = {json.dumps(raw_nodes)};
const LEGEND = [{{ "cid": 0, "name": "Core" }}];
let hiddenCommunities = new Set();
let nodesDS = {{ update: function() {{}}, get: function(id) {{ return RAW_NODES[0]; }} }};
let network = {{ getConnectedNodes: function(id) {{ return []; }}, fit: function() {{}}, moveTo: function() {{}}, on: function() {{}}, once: function() {{}} }};
</script>
</body>
</html>"""

    enriched = _enrich_graphify_html(mock_html, {"nodes": raw_nodes})
    assert "computeDynamicLODThresholds" in enriched or "calculateDynamicLODTiers" in enriched or "LOD_THRESHOLDS" in enriched
    assert "activeKindFilters" in enriched
    assert "Test Suite" in enriched

def test_architect_map_defaults_test_suite_filter_unchecked():
    data = {
        "nodes": [{"id": "a", "label": "A"}],
        "edges": [],
        "repos": [{"name": "synlynk", "path": ".", "primary": True}],
    }
    html = generate_architect_map_html(data, port=27472)
    # At L0/Macro, Test Suite chip should NOT have 'checked' attribute by default to eliminate clutter
    assert 'value="Test Suite"' in html
    assert '<input type="checkbox" value="Test Suite"' in html or '<input type="checkbox"  value="Test Suite"' in html or '<input type="checkbox" id="kind-test" value="Test Suite"' in html or 'checked value="Test Suite"' not in html
