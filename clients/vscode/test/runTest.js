"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const suiteDirectory = path.join(__dirname, "suite");
const testFiles = fs
  .readdirSync(suiteDirectory)
  .filter((file) => file.endsWith(".test.js"))
  .sort()
  .map((file) => path.join(suiteDirectory, file));

const result = spawnSync(
  process.execPath,
  ["--test", ...testFiles],
  { stdio: "inherit" }
);

process.exitCode = result.status === 0 ? 0 : 1;
