"use strict";

function formatStatusText(data = {}) {
  if (data.state === "running") {
    return "$(sync~spin) Synlynk: [" + data.jobId + "] " +
      data.harness + " running (" + (data.elapsedSeconds || 0) + "s)";
  }

  if (data.state === "verifying") {
    return "$(shield) Synlynk: [" + data.jobId + "] " +
      data.harness + " verifying...";
  }

  const spend = typeof data.spend === "number"
    ? "$" + data.spend.toFixed(2)
    : "Ready";
  return "$(circuit-board) Synlynk: Ready (" + spend + ")";
}

class StatusBarController {
  constructor(vscodeStatusBarItem) {
    this.item = vscodeStatusBarItem;
  }

  update(data) {
    if (this.item) {
      this.item.text = formatStatusText(data);
      this.item.show();
    }
  }

  dispose() {
    if (this.item && typeof this.item.dispose === "function") {
      this.item.dispose();
    }
  }
}

module.exports = { formatStatusText, StatusBarController };
