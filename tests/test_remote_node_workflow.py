"""Contract tests for the GitHub Actions EC2 remote-node workflow."""

import json
import subprocess
from pathlib import Path


WORKFLOW = Path(".github/workflows/remote-node.yml")


def _load_workflow():
    proc = subprocess.run(
        ["ruby", "-ryaml", "-rjson", "-e", "puts JSON.generate(YAML.load_file(ARGV[0]))", str(WORKFLOW)],
        check=True,
        capture_output=True,
        text=True,
    )
    doc = json.loads(proc.stdout)
    return doc, doc.get("on") or doc.get("true")


def test_remote_node_workflow_launches_and_self_terminates_ec2_host():
    text = WORKFLOW.read_text(encoding="utf-8")
    doc, trigger = _load_workflow()

    assert "workflow_dispatch" in trigger
    assert "aws-actions/configure-aws-credentials@v4" in text
    assert "permissions:" in text
    assert "id-token: write" in text
    assert "run-instances" in text
    assert "--instance-market-options" in text
    assert "--user-data" in text
    assert "terminate-instances" in text
    assert "create-security-group" in text
    assert "create-key-pair" in text
    assert "delete-security-group" in text
    assert "delete-key-pair" in text
    assert "describe-security-groups" in text
    assert "describe-key-pairs" in text
    assert "ResourceType=security-group" in text
    assert "ResourceType=key-pair" in text
    assert "github.event_name == 'issues'" in text
    assert "github.event.action == 'unlabeled'" in text
    assert "Wait until TTL window ends" in text
    assert "sleep $((TIMEOUT_MINUTES * 60))" in text
    assert "run-remote-node" in text
    assert "trap" in text
    assert "AWS_ACCESS_KEY_ID" not in text
    assert doc["jobs"]["remote-node"]["runs-on"] == "ubuntu-latest"


def test_remote_node_inputs_are_explicit_and_bounded():
    _doc, trigger = _load_workflow()
    inputs = trigger["workflow_dispatch"]["inputs"]

    assert inputs["operation"]["default"] == "launch"
    assert inputs["operation"]["type"] == "choice"
    assert set(inputs["operation"]["options"]) == {"launch", "destroy"}
    assert inputs["instance_type"]["default"] == "t3.micro"
    assert inputs["timeout_minutes"]["default"] <= 30


def test_remote_node_destroy_paths_are_fail_closed():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "always() &&" in text
    assert "inputs.operation == 'destroy'" in text
    assert "inputs.operation == 'launch'" in text
    assert "github.event.action == 'unlabeled'" in text
    assert "exit 1" in text
    assert "describe-instances" in text
