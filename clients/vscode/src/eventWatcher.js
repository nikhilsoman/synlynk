"use strict";

const fs = require("node:fs");
const path = require("node:path");

/**
 * Tail JSON events appended to a workspace's Synlynk event log.
 *
 * Existing log entries are deliberately skipped: callers receive only events
 * written after the watcher is created.
 */
function watchEvents(workspaceRoot, onEvent, options = {}) {
  const synlynkDirectory = path.join(workspaceRoot, ".synlynk");
  const eventsFile = path.join(synlynkDirectory, "events.jsonl");
  const debounceMs = options.debounceMs ?? 200;

  let disposed = false;
  let fileSize = 0;
  let partialLine = "";
  let debounceTimer = null;
  let fileWatcher = null;
  let directoryWatcher = null;
  let workspaceWatcher = null;

  function closeWatcher(watcher) {
    if (!watcher) {
      return null;
    }

    try {
      watcher.close();
    } catch (_) {
      // A concurrently closed watcher needs no further cleanup.
    }
    return null;
  }

  function scheduleRead() {
    if (disposed) {
      return;
    }

    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = null;
      readAppendedEvents();
    }, debounceMs);
  }

  function deliverLines(text) {
    const lines = (partialLine + text).split("\n");
    partialLine = lines.pop();

    for (const line of lines) {
      if (disposed || !line.trim()) {
        continue;
      }

      try {
        onEvent(JSON.parse(line));
      } catch (_) {
        // Ignore malformed JSON and client callback failures so tailing continues.
      }
    }
  }

  function readAppendedEvents() {
    if (disposed) {
      return;
    }

    let nextSize;
    try {
      nextSize = fs.statSync(eventsFile).size;
    } catch (_) {
      return;
    }

    if (nextSize < fileSize) {
      // The log was truncated or replaced. Treat its current contents as known.
      fileSize = nextSize;
      partialLine = "";
      return;
    }
    if (nextSize === fileSize) {
      return;
    }

    const start = fileSize;
    const end = nextSize - 1;
    let contents = "";
    const stream = fs.createReadStream(eventsFile, { start, end, encoding: "utf8" });

    stream.on("data", (chunk) => {
      contents += chunk;
    });
    stream.on("error", () => {
      // The file can be rotated between stat and open; the next filesystem event retries.
    });
    stream.on("end", () => {
      if (disposed) {
        return;
      }
      fileSize = nextSize;
      deliverLines(contents);
    });
  }

  function watchEventsFile() {
    fileWatcher = closeWatcher(fileWatcher);
    try {
      fileWatcher = fs.watch(eventsFile, (eventType) => {
        if (disposed) {
          return;
        }
        if (eventType === "rename") {
          watchCurrentFile();
        }
        scheduleRead();
      });
    } catch (_) {
      // The file may disappear before fs.watch opens it; directory watching retries.
    }
  }

  function watchDirectory() {
    if (directoryWatcher || disposed) {
      return;
    }
    try {
      directoryWatcher = fs.watch(synlynkDirectory, () => watchCurrentFile());
    } catch (_) {
      // A missing .synlynk directory is a supported workspace state.
    }
  }

  function watchCurrentFile() {
    if (disposed) {
      return;
    }

    try {
      fileSize = fs.statSync(eventsFile).size;
      partialLine = "";
      directoryWatcher = closeWatcher(directoryWatcher);
      workspaceWatcher = closeWatcher(workspaceWatcher);
      watchEventsFile();
    } catch (_) {
      fileWatcher = closeWatcher(fileWatcher);
      try {
        fs.statSync(synlynkDirectory);
        watchDirectory();
      } catch (_) {
        directoryWatcher = closeWatcher(directoryWatcher);
        watchWorkspace();
      }
    }
  }

  function watchWorkspace() {
    if (workspaceWatcher || disposed) {
      return;
    }
    try {
      workspaceWatcher = fs.watch(workspaceRoot, () => watchCurrentFile());
    } catch (_) {
      // Invalid or unavailable workspace roots behave as an inert watcher.
    }
  }
  watchCurrentFile();

  return {
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      if (debounceTimer) {
        clearTimeout(debounceTimer);
        debounceTimer = null;
      }
      fileWatcher = closeWatcher(fileWatcher);
      directoryWatcher = closeWatcher(directoryWatcher);
      workspaceWatcher = closeWatcher(workspaceWatcher);
    },
  };
}

module.exports = { watchEvents };
