"use strict";

function formatError(err) {
  if (!err) {
    return { type: "UNKNOWN", message: "Unknown error occurred" };
  }

  const message = err.message || String(err);

  if (
    message.includes("ENOTFOUND") ||
    message.includes("ECONNREFUSED") ||
    message.includes("fetch failed")
  ) {
    return {
      type: "NETWORK_OFFLINE",
      message: `Offline or unreachable API endpoint: ${message}`
    };
  }

  if (message.includes("ENOENT") && message.includes("synlynk")) {
    return {
      type: "CLI_MISSING",
      message:
        "Synlynk CLI binary not found on system PATH. Please run 'pipx install synlynk' or configure synlynk.cliPath."
    };
  }

  if (message.includes("Malformed JSON output")) {
    return { type: "MALFORMED_OUTPUT", message };
  }

  return { type: "EXECUTION_ERROR", message };
}

module.exports = { formatError };
