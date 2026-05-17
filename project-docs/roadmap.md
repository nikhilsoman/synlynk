# synlynk Roadmap

| Phase | Goal | Key Work | Status | Target |
| :--- | :--- | :--- | :--- | :--- |
| v0.2.1: Correctness patch | Make current release trustworthy | Propagate exec exit codes, fix costs.md parser column, remove dead token/cost functions, align install.sh version, expand .gitignore, update roadmap | In Progress | May 2026 |
| v0.3.0: Reliable solo workflow | Make daily use smooth | Subprocess CLI tests, checkpoint idempotency, `synlynk doctor`, shell completions, config validation, watch daemon tradeoff docs | Planned | — |
| v0.4.0: Cost/accountability | Make budget tracking credible | Define one cost schema, provider-specific manual templates, import helpers for known CLI outputs, report stale/missing cost logs | Planned | — |
| v0.5.0: Scoped context | Reduce context noise | `generate_context(scope="task:N")`, task/file filters, per-feature context snapshots, context size reporting | Planned | — |
| v0.6.0: Team-safe docs | Prepare for collaboration | Pull-before-write guardrails, conflict detection, attribution validation, append-only event log backing Markdown views | Planned | — |
| v1.0.0: Stable Lite | Publicly reliable local tool | Freeze CLI/schema, package via pipx or Homebrew, release automation, migration command, full docs, cross-platform compat tests | Planned | — |
