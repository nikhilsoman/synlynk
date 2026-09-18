# Encrypted state.db DR export

**Status:** Approved for implementation by Home Harness

## Thesis

Create a provider-neutral, encrypted export from a verified SQLite snapshot so
the artifact can be retained on an offline or cloud-backed filesystem without
making GitHub, Google Drive, or iCloud the source of truth.

## Design

- `synlynk backup encrypt <snapshot> --output-dir <dir> --recipient <gpg recipient>`
  encrypts an already verified snapshot with GnuPG public-key encryption.
- Encryption is fail-closed: the source must pass `verify_snapshot`, the
  recipient is required, and plaintext output is never copied to the export
  destination.
- The encrypted artifact gets a JSON manifest containing the source SHA-256,
  encrypted SHA-256, recipient identifier, and verification timestamp.
- Verification decrypts to a temporary file, runs SQLite integrity checks and
  source-manifest comparisons, then removes plaintext before returning.
- Destination sync remains outside Synlynk. Users can place the output
  directory on an encrypted external disk, iCloud Drive, Google Drive, or a
  private GitHub-managed backup repository. The encrypted artifact is the only
  object that should leave the machine.

## Non-goals

- No cloud OAuth, hosted service, GitHub release automation, or plaintext
  upload.
- No passphrase embedded in CLI arguments, manifests, or repository files.
- No deletion or replacement of the canonical database.

## Success criteria

An encrypted export can be created and independently verified on a machine
with the matching private key; tampering, missing GPG, wrong recipient, or
manifest mismatch fails closed; no plaintext temporary file remains after
success or failure.
