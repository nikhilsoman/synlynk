---
title: "Why I built synlynk"
date: 2026-05-10
excerpt: "Three AI tools. Three separate contexts. Zero shared memory. There had to be a better way."
tags: posts
---

Every AI session starts from scratch. 

I use **Claude Code** for architectural planning, **Gemini CLI** for high-volume file processing, and **Cursor** for the final implementation. Each tool is world-class, but they are all essentially stateless islands. 

When I switch from Claude to Gemini, I have to re-explain the task. I have to copy-paste the latest decisions. I have to manually update the todo list. This "context tax" was slowing me down and wasting tokens.

### The Pain Points

1. **Context Loss:** Switching tools meant re-uploading the world.
2. **Invisible Costs:** No easy way to see how much I'd spent across tools in a single session.
3. **Task Drift:** Keeping `todo.md` updated was a manual chore that I often skipped.
4. **Hallucination Loops:** AI agents would occasionally get stuck in a "flatline" loop, repeatedly failing the same command while I wasn't looking.

### The Solution: synlynk

I built **synlynk** as a "Context Switchboard." It's not another AI tool; it's the connective tissue between them. 

By wrapping my existing tools (e.g., `synlynk exec claude`), I ensure that a single, unified project snapshot is always available. The AI tool is instructed to read `.synlynk/context.md` at the start of every session. 

It keeps the memory alive, the costs visible, and the tasks in sync.

### stdlib-only
I made a deliberate choice to keep synlynk a single-file Python CLI with **zero dependencies**. No `pip install`, no environment hell. Just a simple `curl | bash` and you're ready to build.

Stay tuned for more updates as we move toward the v0.2.0 release.
