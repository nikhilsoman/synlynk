"""Compare warm-cache lookup with the live graph walk on a fixture graph.

The fixture is built in a temp directory. This script does not call graphify
and does not read the live synlynk graph.
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def cache_median_is_faster(cache_times: list[float], live_times: list[float]) -> bool:
    """True only when the cache series has a strictly lower median."""
    if not cache_times or not live_times:
        return False
    return statistics.median(cache_times) < statistics.median(live_times)


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return ordered[index]


def _fixture_repo(root: Path) -> None:
    nodes = []
    edges = []
    nodes.append({
        "id": "cli",
        "label": "main",
        "file": "synlynk/cli.py",
        "kind": "function",
        "signature": "def main():",
    })
    for index in range(30):
        node_id = f"sym{index}"
        nodes.append({
            "id": node_id,
            "label": f"symbol_{index}",
            "file": f"synlynk/mod_{index}.py",
            "kind": "function",
            "signature": f"def symbol_{index}():",
        })
        edges.append({"source": "cli" if index == 0 else f"sym{index - 1}", "target": node_id})
    nodes.append({
        "id": "route",
        "label": "GET /health",
        "file": "synlynk/http.py",
        "kind": "route",
        "signature": "GET /health",
    })
    edges.append({"source": "route", "target": "sym0"})
    out = root / ".synlynk" / "graphify-out"
    out.mkdir(parents=True)
    (out / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": edges}))
    (out / "manifest.json").write_text(json.dumps({
        "built_at_commit": "fixture",
        "lifecycle": "brownfield",
        "node_count": len(nodes),
    }))


def _queries() -> list[str]:
    queries = []
    for index in range(50):
        if index % 2 == 0:
            queries.append("main cli symbol scan")
        else:
            queries.append(f"unrelated topic {index} zebra")
    return queries


def run_benchmark() -> dict:
    from synlynk.graph_cache import lookup_traversal, write_traversal_cache
    from synlynk.pack import _extract_keywords, synthesize_context_pack

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fixture_repo(root)
        write_traversal_cache(str(root))
        cache_file = root / ".synlynk" / "graph-cache" / "traversals.json"
        cache_bytes = cache_file.read_bytes()
        queries = _queries()
        cache_times = []
        live_times = []
        cache_chars = []
        live_chars = []
        for query in queries:
            keywords = _extract_keywords(query)
            started = time.perf_counter()
            hit = lookup_traversal(str(root), keywords)
            cache_times.append(time.perf_counter() - started)
            cache_chars.append(len(json.dumps(hit)) if hit else 0)

            cache_file.unlink()
            started = time.perf_counter()
            live = synthesize_context_pack(str(root), task_text=query)
            live_times.append(time.perf_counter() - started)
            live_chars.append(len(live))
            cache_file.write_bytes(cache_bytes)

        rss = None
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except Exception:
            rss = None
        return {
            "queries": len(queries),
            "nodes": 32,
            "cache_median_s": statistics.median(cache_times),
            "cache_p95_s": _percentile(cache_times, 0.95),
            "live_median_s": statistics.median(live_times),
            "live_p95_s": _percentile(live_times, 0.95),
            "cache_output_chars_median": statistics.median(cache_chars),
            "live_output_chars_median": statistics.median(live_chars),
            "ru_maxrss": rss,
            "cache_faster": cache_median_is_faster(cache_times, live_times),
            "platform": platform.platform(),
        }


def main() -> None:
    stats = run_benchmark()
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
