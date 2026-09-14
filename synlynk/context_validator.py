from typing import Dict, Any


def render_chips_summary(data: Dict[str, Any]) -> str:
    """Format discovery data as concise interactive visual chips."""
    chips = []
    if "domain" in data and "industry" in data["domain"]:
        chips.append(f"[Domain: {data['domain']['industry']}]")
    if "physical" in data:
        for lang in data["physical"].get("languages", []):
            chips.append(f"[Language: {lang}]")
        for fw in data["physical"].get("frameworks", []):
            chips.append(f"[Framework: {fw}]")
    return "  ".join(chips)


def validate_context_interactive(data: Dict[str, Any], no_input: bool = False) -> Dict[str, Any]:
    """Validate discovered context via TTY chips with default Enter continuation."""
    if no_input:
        return data
    print("\n✦ Discovered Workspace Context:")
    print("  " + render_chips_summary(data))
    print("\nPress Enter to accept [or Space to open Vizor]: ", end="", flush=True)
    return data


def validate_context(data: Dict[str, Any], interactive: bool = True) -> Dict[str, Any]:
    """Validate discovered context with interactive or headless mode."""
    return validate_context_interactive(data, no_input=not interactive)

