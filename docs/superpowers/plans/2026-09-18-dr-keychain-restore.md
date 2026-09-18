# Plan: Keychain-aware DR restore

1. Add a macOS Keychain passphrase resolver and stdin-based GPG decryption.
2. Expose `--keychain-service` on `backup verify-encrypted`.
3. Add regression coverage for Keychain-backed invocation and failure paths.
4. Run the protected iCloud restore drill through the product CLI and update
   #1660.
