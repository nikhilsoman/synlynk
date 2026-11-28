"""Canonical taxonomy and parity checks for harness dispatch rejection paths."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class DispatchRejection:
    """The operator-facing contract for one preflight rejection sentinel."""

    category: str
    remediation: str
    modes: tuple[str, ...] = ("interactive", "headless")


HARNESS_DISPATCH_REJECTION_TAXONOMY = {
    "HARNESS_PREFLIGHT_FAIL": DispatchRejection(
        "harness_preflight", "repair the harness, authentication, flags, or endpoint and retry"
    ),
    "LOCAL_CAPABILITY_UNAVAILABLE": DispatchRejection(
        "local_capability", "run synlynk local doctor and restore the local model endpoint"
    ),
    "LOCAL_ORBSTACK_UNAVAILABLE": DispatchRejection(
        "local_runtime", "start OrbStack or disable the containerized local configuration"
    ),
    "INSTRUCTION_FILE_MISSING": DispatchRejection(
        "instruction_file", "run synlynk init or provide the required instruction file"
    ),
    "MCP_SERVER_MISSING": DispatchRejection(
        "mcp_capability", "configure the declared MCP server or remove the requirement"
    ),
    "CAPACITY_EXCEEDED_INPUT": DispatchRejection(
        "capacity_input", "reduce the task context or choose a harness with more input capacity"
    ),
    "CAPACITY_EXCEEDED_OUTPUT": DispatchRejection(
        "capacity_output", "reduce the task scope or choose a harness with more output capacity"
    ),
    "GOVERNS_LINKAGE_MISSING": DispatchRejection(
        "governs_linkage", "link the dispatch to a story, issue, or pull request"
    ),
    "HARNESS_MANIFEST_REVALIDATION_FAILED": DispatchRejection(
        "manifest_revalidation", "probe the harness manifest again or use the explicit force override"
    ),
}


def _preflight_function_nodes(source: str) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(source)
    return [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"_dispatch_capability_preflight", "_preflight_dispatch"}
    ]


def discover_dispatch_rejection_sentinels(source: str) -> set[str]:
    """Return sentinel values emitted by the two dispatch preflight functions."""
    found: set[str] = set()
    for function in _preflight_function_nodes(source):
        for node in ast.walk(function):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "sentinel"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    found.add(value.value)
    return found


def validate_headless_contract_parity(baselines: Mapping[str, Mapping]) -> list[str]:
    """Validate that each harness describes both sides of its dispatch contract.

    Interactive execution is represented by the ordinary CLI configuration;
    headless execution is represented by ``headless_contract`` and
    ``non_interactive_flags``.  The check deliberately stays structural so it
    can run without invoking vendor CLIs or requiring credentials.
    """
    errors: list[str] = []
    for harness, baseline in baselines.items():
        cli = baseline.get("cli")
        dispatch_flags = baseline.get("dispatch_flags")
        contract = baseline.get("headless_contract")
        non_interactive_flags = baseline.get("non_interactive_flags")
        if not cli:
            errors.append(f"{harness}: missing interactive cli")
        if not isinstance(dispatch_flags, dict):
            errors.append(f"{harness}: missing dispatch_flags")
        if not isinstance(contract, dict):
            errors.append(f"{harness}: missing headless_contract")
            continue
        if not contract.get("non_interactive_flag"):
            errors.append(f"{harness}: missing headless non_interactive_flag")
        if not isinstance(non_interactive_flags, list):
            errors.append(f"{harness}: non_interactive_flags must be a list")
        invalid = set((dispatch_flags or {}).get("invalid_flags", []))
        if invalid.intersection(non_interactive_flags or []):
            errors.append(f"{harness}: a headless flag is also marked invalid")
    return errors
