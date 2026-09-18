# State DB disaster-recovery runbook

This runbook is the operational procedure for recovering Synlynk context on a
second machine. The canonical database is the registry-selected `state.db`;
do not copy an arbitrary worktree or legacy database into place.

## Recovery model

- One stable GPG keypair is used per product/workspace.
- The public-key fingerprint is recorded in the DR ticket and backup manifest.
- The private key is kept offline or in the operator's secure key store. It is
  never committed to GitHub, Google Drive, iCloud, or the repository.
- Rotate the keypair only for compromise, loss, or an intentional rotation.
  Keep old public keys available while old packages are retained.
- Retain at least two encrypted copies in independent destinations. GitHub
  private release/artifact storage, Google Drive, and an iCloud-synced folder
  are provider options; none is the source of truth and no hosted Vizor is
  required.

## Create an encrypted package

On the healthy machine, verify the current state first:

```bash
synlynk state inventory --all
synlynk status
```

Create a package with the DR public-key fingerprint (or an accepted GPG
recipient identifier):

```bash
synlynk backup package \
  --recipient '<DR_PUBLIC_KEY_FINGERPRINT>' \
  --output-dir /path/to/offline-dr/state
```

The command creates an online SQLite snapshot, verifies its integrity, encrypts
it, writes a checksum manifest, and removes the temporary plaintext. Copy the
`.db.gpg` and matching `.json` files to at least two independent destinations.
Upload only those encrypted files. Record the artifact names, SHA-256 values,
creation time, key fingerprint, and destinations in the DR ticket.

The lower-level commands remain available when investigating a package:

```bash
synlynk backup create --output-dir /path/to/offline-dr/state
synlynk backup verify /path/to/offline-dr/state/state-<timestamp>.db
synlynk backup encrypt /path/to/offline-dr/state/state-<timestamp>.db \
  --recipient '<DR_PUBLIC_KEY_FINGERPRINT>'
```

## Second-machine restore drill

1. Install the same Synlynk release (or a newer release whose state schema is
   compatible) on a clean machine.
2. Import the DR private key through the local secure key store. Do not place
   the private key in the repository or synced backup folder.
3. Download the encrypted artifact and matching manifest from a destination.
4. Verify the encrypted artifact before restoring:

   ```bash
   synlynk backup verify-encrypted \
     /path/to/state-<timestamp>.db.gpg \
     --keychain-service '<KEYCHAIN_SERVICE>'
   ```

   If the key is protected without macOS Keychain, use the local GPG agent and
   omit `--keychain-service`.
5. Decrypt to a local temporary path with GPG. Keep that plaintext path outside
   the repository and remove it after the restore is complete.
6. Run a dry-run restore. Use the canonical destination returned by
   `synlynk state inventory` on the new machine:

   ```bash
   synlynk state restore /tmp/state-snapshot.db \
     /path/to/canonical/state.db \
     --slug '<PRODUCT_SLUG>' \
     --product-id '<PRODUCT_ID>'
   ```

7. Review the dry-run archive and lineage information. Apply only when the
   destination and product identity are correct:

   ```bash
   synlynk state restore /tmp/state-snapshot.db \
     /path/to/canonical/state.db \
     --slug '<PRODUCT_SLUG>' \
     --product-id '<PRODUCT_ID>' \
     --apply
   ```

8. Verify the recovered state and registry lineage:

   ```bash
   synlynk state inventory --all
   synlynk status
   synlynk checkpoint
   ```

9. Record the result, elapsed time, restored snapshot hash, row-count evidence,
   and any follow-up in the DR ticket. Remove temporary plaintext and confirm
   that no private key or plaintext database was uploaded.

## Drill acceptance criteria

The drill passes when the encrypted artifact checksum verifies, decryption
passes SQLite integrity checks, the restore is dry-run reviewed before apply,
the canonical registry points to the recovered database, `synlynk status` and
`synlynk checkpoint` succeed, and the evidence is recorded. Until a second
machine is available, the package creation and verification portions can be
run locally; the cross-machine restore remains explicitly pending.
