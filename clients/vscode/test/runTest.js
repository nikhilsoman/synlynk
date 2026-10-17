"use strict";

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const result = spawnSync(
  process.execPath,
  ["--test", path.join(__dirname, "suite", "scaffolding.test.js")],
  { stdio: "inherit" }
);

process.exitCode = result.status === 0 ? 0 : 1;
