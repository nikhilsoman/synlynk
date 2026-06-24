# synlynk 101

**Audience:** Experienced dev, new to AI coding — using AI at the level of writing unit tests, sample code searches, some skills. Has heard of OpenClaw, GStack, etc.

---

**Where you are right now:** AI is a tool you reach for. You describe what you want, it drafts something, you judge it, integrate it, move on. Useful, but you're still the one holding everything together.

**The problem synlynk solves:** When you want AI to do more than answer questions — to actually *run* a coding task start to finish — you hit a wall. The AI doesn't know your project budget, doesn't know when it's spinning its wheels, doesn't know what already happened, can't decide when to stop and ask. You end up babysitting it. That's not autonomy, that's narrated autocomplete.

synlynk is the missing OS layer. It gives an AI agent the same things a human developer takes for granted:

- **A project context** — what this codebase is, what the current task is, what's been done
- **A budget and cost tracking** — how many tokens you've spent, what your burn rate is, when to stop
- **Health signals** — is the agent stuck in a loop? Has it hit a rate limit? Is it stalled?
- **A gate before it runs** — if there's a CRITICAL alert (quota exhausted, zombie process), exec is blocked until you clear it
- **A log of what happened** — telemetry per exec: command, exit code, tokens, timestamp

You run it like: `synlynk exec claude -- --print "write tests for auth.py"`. synlynk wraps that call, injects project context, captures the output, scrapes token usage, writes to the cost ledger, checks for patterns (is this command failing 3 times in a row?), and reports health on the next `synlynk status`.

**How it relates to OpenClaw, GStack, etc.:** Those are the *agents* — the things that actually write code, run commands, make decisions. synlynk is the *substrate* they run on. Think of it like: OpenClaw is an application; synlynk is the OS it installs on. Without the OS layer, every agent has to reinvent budget tracking, context injection, health monitoring, and audit trails. synlynk makes those primitives available to all of them.

**What the path looks like from where you are:**

Right now you're prompting manually. The next step is letting an agent own a task — "write all the unit tests for this module" — while synlynk makes sure it doesn't overspend, doesn't loop, and you can see what happened. After that, you chain tasks: Architect designs, Builder implements, Verifier checks. That pipeline (the Trio Protocol) is what v0.4.0 ships.

The ambition is that eventually `synlynk run <task>` dispatches the right agent for the job, routes it through conventions your team has agreed on, tracks cost attribution to the story being worked, and surfaces a result for human review — with a full audit trail. You stay in control of the decisions; the agents do the execution.

**Concretely:** synlynk today is a single Python script, zero dependencies, you drop it in your path. `synlynk init` in a repo, `synlynk exec <agent-command>` to run AI with guardrails, `synlynk status` to see what's happening. That's the entry point.
