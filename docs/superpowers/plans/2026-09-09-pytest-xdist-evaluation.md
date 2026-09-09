# pytest-xdist Evaluation Plan (#1496)

1. Read #1496 and the post-#1494/#1495 workflow and Actions timing evidence.
2. Run the exact serial workflow selection and collect its result and duration.
3. Install xdist only in an isolated experiment environment and repeat bounded
   and automatic worker runs without retries or failure masking.
4. Classify test modules by shared-state and subprocess risk, including the
   known live-selftest mutation failure.
5. Document the evidence, scoped opt-in strategy, CI resource/diagnostic risks,
   and the independently revertible serial rollback boundary.
6. Run focused documentation/configuration checks, commit, push, and open a
   PR linked to #1496 with the measured verification details.
