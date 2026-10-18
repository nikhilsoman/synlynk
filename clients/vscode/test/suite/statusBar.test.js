"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");
const {
  formatStatusText,
  StatusBarController,
} = require("../../src/ui/statusBar");

describe("StatusBarController", () => {
  it("formats idle state with spend metric", () => {
    assert.equal(
      formatStatusText({ state: "idle", spend: 18.47 }),
      "$(circuit-board) Synlynk: Ready ($18.47)"
    );
  });

  it("formats an active running dispatch state", () => {
    assert.equal(
      formatStatusText({
        state: "running",
        jobId: "djob-8f2a",
        harness: "Codex",
        elapsedSeconds: 32,
      }),
      "$(sync~spin) Synlynk: [djob-8f2a] Codex running (32s)"
    );
  });

  it("formats the verification stage", () => {
    assert.equal(
      formatStatusText({
        state: "verifying",
        jobId: "djob-8f2a",
        harness: "Grok",
      }),
      "$(shield) Synlynk: [djob-8f2a] Grok verifying..."
    );
  });

  it("updates and shows its status bar item", () => {
    const item = {
      showCount: 0,
      show() { this.showCount += 1; },
    };
    const controller = new StatusBarController(item);

    controller.update({ state: "idle" });

    assert.equal(item.text, "$(circuit-board) Synlynk: Ready (Ready)");
    assert.equal(item.showCount, 1);
  });

  it("disposes its status bar item when supported", () => {
    const item = {
      disposeCount: 0,
      dispose() { this.disposeCount += 1; },
    };
    const controller = new StatusBarController(item);

    controller.dispose();

    assert.equal(item.disposeCount, 1);
  });
});
