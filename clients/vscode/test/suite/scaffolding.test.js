"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const extensionRoot = path.resolve(__dirname, "../..");
const packagePath = path.join(extensionRoot, "package.json");

function readManifest() {
  return JSON.parse(fs.readFileSync(packagePath, "utf8"));
}

test("package manifest has the required extension metadata", () => {
  assert.ok(fs.existsSync(packagePath), "package.json must exist");
  const pkg = readManifest();

  assert.equal(pkg.name, "synlynk-vscode");
  assert.equal(pkg.publisher, "synlynk");
  assert.equal(pkg.version, "0.1.0");
  assert.equal(pkg.main, "./extension.js");
  assert.equal(pkg.engines.vscode, "^1.85.0");
  assert.ok(pkg.scripts.test);
  assert.ok(pkg.scripts.package);
});

test("package manifest has zero runtime dependencies", () => {
  const pkg = readManifest();
  assert.deepEqual(pkg.dependencies, {});
});

test("package manifest contributes the Synlynk sidebar and required views", () => {
  const pkg = readManifest();
  const { contributes } = pkg;
  const containers = contributes.viewsContainers.activitybar;
  const sidebar = containers.find((container) => container.id === "synlynk-sidebar");

  assert.ok(sidebar, "Must declare the synlynk-sidebar activity bar container");
  assert.equal(sidebar.icon, "media/synlynk-icon.svg");
  assert.ok(contributes.views["synlynk-sidebar"], "Must contribute sidebar views");

  const viewIds = contributes.views["synlynk-sidebar"].map((view) => view.id);
  assert.deepEqual(viewIds, ["synlynk-fleet", "synlynk-goals", "synlynk-jobs"]);
});

test("packaging assets and exclusions exist", () => {
  assert.ok(fs.existsSync(path.join(extensionRoot, ".vscodeignore")));
  assert.ok(fs.existsSync(path.join(extensionRoot, "media", "synlynk-icon.svg")));
});
