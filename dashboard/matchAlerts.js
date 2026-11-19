// Keep group IDs through the whole news window, including when a capped feed temporarily omits one.
export function newMatchTracker() {
  return { asOf: null, seenUntil: new Map() };
}

export function newReportMatches(snapshot, tracker, now) {
  if (!snapshot || (tracker.asOf !== null && snapshot.as_of < tracker.asOf))
    return [];
  const first = tracker.asOf === null;
  tracker.asOf = snapshot.as_of;
  for (const [id, until] of tracker.seenUntil) {
    if (until < now) tracker.seenUntil.delete(id);
  }
  const arrivals = [];
  for (const row of snapshot.records) {
    if (
      row.kind !== "candidate" ||
      row.published_at + snapshot.window_seconds < now
    )
      continue;
    const isReport = (source) =>
      Boolean(source && source !== "bluesky" && source !== "sec");
    if (!isReport(row.source) && !row.evidence?.some((e) => isReport(e.source)))
      continue;
    const seen = tracker.seenUntil.has(row.id);
    tracker.seenUntil.set(
      row.id,
      Math.max(
        tracker.seenUntil.get(row.id) || 0,
        row.published_at + snapshot.window_seconds,
      ),
    );
    if (!seen && !first && now - snapshot.as_of <= 75) arrivals.push(row);
  }
  return arrivals.sort((a, b) => b.detected_at - a.detected_at);
}

export function playChime(context) {
  if (!context || context.state !== "running") return;
  for (const [offset, frequency] of [
    [0, 660],
    [0.16, 880],
  ]) {
    const start = context.currentTime + offset;
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(frequency, start);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(0.09, start + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.23);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.onended = () => {
      oscillator.disconnect();
      gain.disconnect();
    };
    oscillator.start(start);
    oscillator.stop(start + 0.24);
  }
}
