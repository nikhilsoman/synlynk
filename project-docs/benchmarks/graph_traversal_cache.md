# Graph traversal cache benchmark

Recorded 2026-10-27 from one local run of `python3 scripts/benchmark_graph_cache.py`.

- Machine: macOS-27.0.1-arm64-arm-64bit-Mach-O
- Fixture: 32 nodes, 50 queries, temp directory. No `graphify` subprocess and not the live synlynk graph.
- Half the queries are `main cli symbol scan` (expected cache hits). Half are unrelated tokens (expected misses).
- `ru_maxrss` is `resource.getrusage` on this Mac, which reports bytes.

| Path | Median | p95 | Median output chars |
|---|---:|---:|---:|
| Cache lookup | 0.079 ms | 0.083 ms | 298 |
| Live walk | 0.096 ms | 0.120 ms | 757 |

Peak `ru_maxrss`: 43171840 bytes.

The cache median is lower than the live-walk median on this fixture. Both numbers are sub-millisecond because the graph is tiny. This note does not claim a production latency SLO or a disk-size reduction.
