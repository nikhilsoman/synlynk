# Keychain-aware encrypted DR restore

**Status:** Approved for implementation by Home Harness

## Decision

The encrypted restore command accepts an optional macOS Keychain service name.
When supplied, Synlynk retrieves the passphrase with `security`, passes it to
GPG through stdin, and never places it in argv, manifests, or logs. Without the
option, existing GPG-agent behavior remains unchanged.

## Safety

- Keychain lookup fails closed on non-macOS systems or missing services.
- Decryption still occurs only in a temporary directory and is followed by
  SQLite integrity and source-checksum verification.
- This does not upload private keys or make a cloud provider the source of
  truth.

## Success condition

The protected workspace key generated for #1660 can restore an encrypted
snapshot through the product CLI on macOS, with no plaintext left behind.
