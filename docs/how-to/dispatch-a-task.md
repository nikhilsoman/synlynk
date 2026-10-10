# How to dispatch a task

Write the task as a small outcome with a verification command:

```bash
synlynk dispatch --task "Add the parser test; verify with pytest tests/test_cli_parser.py -v"
```

Keep unrelated cleanup out of the task. Synlynk can infer the role and harness
from the task and project policy; specify them when the routing decision is
important:

```bash
synlynk dispatch codex --as-agent dev --task "Implement the parser test"
```

Use `synlynk jobs` to find the job and its isolated worktree after dispatch.
