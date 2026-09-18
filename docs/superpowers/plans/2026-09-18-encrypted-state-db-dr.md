# Plan: encrypted state.db DR export

1. Add GPG subprocess helpers with argument-safe invocation and temporary-file
   cleanup.
2. Add `backup encrypt` and `backup verify-encrypted` CLI commands and taxonomy.
3. Add tests using a temporary GPG home/keypair when GPG is available, plus
   fail-closed tests for missing recipients and tampered artifacts.
4. Document provider-neutral retention guidance and verify the complete local
   recovery path.
