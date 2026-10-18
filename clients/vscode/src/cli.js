"use strict";

const { execFile } = require("node:child_process");
const { formatError } = require("./util/errorBoundary");

const MINIMUM_VERSION = [0, 23, 0];

function parseCliJson(stdout, subcommand) {
  try {
    return JSON.parse(stdout);
  } catch (_) {
    throw new Error(`Malformed JSON output from synlynk ${subcommand}: ${stdout}`);
  }
}

function runSynlynk(subcommand, args = [], options = {}) {
  const binary = options.cliPath || "synlynk";
  const isVersionRequest = subcommand === "--version";
  const commandArgs = isVersionRequest
    ? [subcommand, ...args]
    : [subcommand, ...args, "--json"];

  return new Promise((resolve, reject) => {
    execFile(
      binary,
      commandArgs,
      {
        cwd: options.cwd || process.cwd(),
        timeout: options.timeout || 30_000,
        maxBuffer: 10 * 1024 * 1024,
        ...options.execOptions
      },
      (err, stdout, stderr) => {
        if (err) {
          reject(formatError(new Error(stderr || err.message)));
          return;
        }

        if (isVersionRequest) {
          resolve({ version: stdout.trim().replace(/^synlynk\s+v?/i, "") });
          return;
        }

        try {
          resolve(parseCliJson(stdout, subcommand));
        } catch (parseErr) {
          reject(formatError(parseErr));
        }
      }
    );
  });
}

function parseSemver(version) {
  const match = String(version || "").match(/(\d+)\.(\d+)\.(\d+)/);
  return match
    ? [Number.parseInt(match[1], 10), Number.parseInt(match[2], 10), Number.parseInt(match[3], 10)]
    : [0, 0, 0];
}

function isAtLeast(version, minimum) {
  for (let index = 0; index < minimum.length; index += 1) {
    if (version[index] !== minimum[index]) {
      return version[index] > minimum[index];
    }
  }
  return true;
}

async function checkCliCompatibility(runner = runSynlynk, options = {}) {
  try {
    const data = await runner("--version", [], options);
    const version = typeof data === "string" ? data : data.version || "0.0.0";

    if (isAtLeast(parseSemver(version), MINIMUM_VERSION)) {
      return { compatible: true, version };
    }

    return {
      compatible: false,
      version,
      error: `Upgrade required: detected synlynk v${version}, but >= v0.23.0 is required.`
    };
  } catch (err) {
    const formatted = formatError(err);
    return { compatible: false, version: "unknown", error: formatted.message };
  }
}

module.exports = { runSynlynk, parseCliJson, checkCliCompatibility };
