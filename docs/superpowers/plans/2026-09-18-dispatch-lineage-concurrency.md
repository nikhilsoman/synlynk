# Plan: dispatch lineage concurrency

1. Add process/file locking around lineage schema and write transactions.
2. Stop mutating journal mode in each lineage connection.
3. Add cleanup-safe connection handling and run the concurrency regression
   repeatedly.
4. Open a focused PR linked to #1499 and record the RCA evidence.
