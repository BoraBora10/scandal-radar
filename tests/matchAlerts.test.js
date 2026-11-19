import test from "node:test";
import assert from "node:assert/strict";
import {
  newMatchTracker,
  newReportMatches,
  playChime,
} from "../dashboard/matchAlerts.js";

const row = (id, source = "google", kind = "candidate") => ({
  id,
  source,
  kind,
  published_at: 100,
  detected_at: 110,
  evidence: [{ source }],
});
const snapshot = (as_of, records) => ({
  as_of,
  window_seconds: 21600,
  records,
});

test("baseline, repeated snapshots, older responses and reappearing events are quiet", () => {
  const tracker = newMatchTracker(),
    existing = row("old"),
    next = row("new");
  const advance = (at, records) =>
    newReportMatches(snapshot(at, records), tracker, at);
  assert.deepEqual(advance(130, [existing]), []);
  assert.deepEqual(advance(140, [existing, next]), [next]);
  assert.deepEqual(advance(140, [existing, next]), []);
  assert.deepEqual(advance(135, [row("out-of-order")]), []);
  advance(145, []);
  assert.deepEqual(advance(150, [next]), []);
});
test("only active report candidates alert, including an existing social story picked up by news", () => {
  const tracker = newMatchTracker(),
    social = row("post", "bluesky");
  newReportMatches(snapshot(120, []), tracker, 120);
  assert.deepEqual(
    newReportMatches(
      snapshot(130, [
        row("wire", "pr", "wire"),
        row("filing", "sec", "filing"),
        social,
      ]),
      tracker,
      130,
    ),
    [],
  );
  const confirmed = {
    ...social,
    evidence: [...social.evidence, { source: "pr" }],
  };
  assert.deepEqual(newReportMatches(snapshot(150, [confirmed]), tracker, 150), [
    confirmed,
  ]);
  assert.deepEqual(
    newReportMatches(snapshot(160, [row("stale")]), tracker, 500),
    [],
  );
  assert.deepEqual(
    newReportMatches(snapshot(30000, [row("expired")]), tracker, 30000),
    [],
  );
});
test("each chime schedules two limited-duration tones only on an active audio context", () => {
  const starts = [],
    stops = [];
  const gain = { setValueAtTime() {}, exponentialRampToValueAtTime() {} };
  const ctx = {
    state: "suspended",
    currentTime: 10,
    createGain: () => ({ gain, connect() {}, disconnect() {} }),
    createOscillator: () => ({
      frequency: gain,
      connect() {},
      disconnect() {},
      start: (t) => starts.push(t),
      stop: (t) => stops.push(t),
    }),
  };
  playChime(ctx);
  assert.equal(starts.length, 0);
  ctx.state = "running";
  playChime(ctx);
  assert.deepEqual(starts, [10, 10.16]);
  assert.equal(stops.length, 2);
  assert.ok(stops[1] < 10.5);
});
