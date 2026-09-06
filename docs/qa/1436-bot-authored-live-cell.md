# #1436 Bot-Authored Live Cell

This PR exists solely to prove the remaining live cell from #1436: a
role-token dispatch can create a pull request authored by
`synlynk-synlynk-dev[bot]`, rather than by `nikhilsoman`.

There is no implementation change here. The small documentation payload is
intentionally unique to this verification PR. QA should validate that the PR
is open, that its author is the dev App bot, and that the qa App can approve
it. This PR must remain unmerged until that approval test is complete.
