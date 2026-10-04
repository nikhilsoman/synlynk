# How to inspect and review results

1. Run `synlynk jobs` and identify the completed job.
2. Run `synlynk status` to see the workspace and verification state.
3. Inspect the job's changed files and test output in its worktree.
4. Review the resulting pull request before merging.

The Agent owns the decision and accountability; the Harness only supplies the
execution backend. Keep that distinction in mind when interpreting attribution
or changing routing. See the [role-vs-harness glossary](../glossary-agent-vs-harness.md).
