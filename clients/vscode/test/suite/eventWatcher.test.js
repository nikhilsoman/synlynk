"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { afterEach, describe, it } = require("node:test");
const { watchEvents } = require("../../src/eventWatcher");

const temporaryDirectories = [];

function createWorkspace({ createSynlynkDirectory = true } = {}) {
  const workspaceRoot = fs.mkdtempSync(path.join(os.tmpdir(), "synlynk-event-test-"));
  temporaryDirectories.push(workspaceRoot);

  const synlynkDirectory = path.join(workspaceRoot, ".synlynk");
  if (createSynlynkDirectory) {
    fs.mkdirSync(synlynkDirectory);
  }

  return {
    workspaceRoot,
    eventsFile: path.join(synlynkDirectory, "events.jsonl"),
  };
}

function waitFor(predicate, timeoutMs = 1000) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const timer = setInterval(() => {
      if (predicate()) {
        clearInterval(timer);
        resolve();
      } else if (Date.now() >= deadline) {
        clearInterval(timer);
        reject(new Error("Timed out waiting for event watcher output"));
      }
    }, 10);
  });
}

afterEach(() => {
  while (temporaryDirectories.length > 0) {
    fs.rmSync(temporaryDirectories.pop(), { recursive: true, force: true });
  }
});

describe("Reactive Event-Tailing Substrate", () => {
  it("handles missing events files and directories gracefully", () => {
    const missingFile = createWorkspace();
    const missingDirectory = createWorkspace({ createSynlynkDirectory: false });

    const fileWatcher = watchEvents(missingFile.workspaceRoot, () => {});
    const directoryWatcher = watchEvents(missingDirectory.workspaceRoot, () => {});

    assert.equal(typeof fileWatcher.dispose, "function");
    assert.equal(typeof directoryWatcher.dispose, "function");
    fileWatcher.dispose();
    directoryWatcher.dispose();
  });

  it("tails and parses only JSON events appended after watching begins", async () => {
    const { workspaceRoot, eventsFile } = createWorkspace();
    fs.writeFileSync(eventsFile, '{"event":"initial"}\n');

    const received = [];
    const watcher = watchEvents(workspaceRoot, (event) => received.push(event), {
      debounceMs: 10,
    });

    await new Promise((resolve) => setTimeout(resolve, 30));
    fs.appendFileSync(
      eventsFile,
      '{"event":"job_started","job_id":"djob-1"}\n{"event":"job_finished","job_id":"djob-1"}\n',
    );

    await waitFor(() => received.length === 2);
    watcher.dispose();

    assert.deepEqual(received, [
      { event: "job_started", job_id: "djob-1" },
      { event: "job_finished", job_id: "djob-1" },
    ]);
  });

  it("ignores malformed lines and prevents callbacks after disposal", async () => {
    const { workspaceRoot, eventsFile } = createWorkspace();
    fs.writeFileSync(eventsFile, "");

    const received = [];
    const watcher = watchEvents(workspaceRoot, (event) => received.push(event), {
      debounceMs: 30,
    });

    fs.appendFileSync(eventsFile, "not-json\n");
    watcher.dispose();
    fs.appendFileSync(eventsFile, '{"event":"must_not_arrive"}\n');

    await new Promise((resolve) => setTimeout(resolve, 100));
    assert.deepEqual(received, []);
  });
});
