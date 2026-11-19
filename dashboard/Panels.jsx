import React, { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Bell,
  CheckCheck,
  ChevronRight,
  CircleCheck,
  CircleDot,
  Crosshair,
  ListFilter,
  Minus,
  Pause,
  Play,
  Radio,
  RadioTower,
  ScanLine,
  ShieldCheck,
  SlidersHorizontal,
  TerminalSquare,
  Waves,
} from "lucide-react";
import { Scope, Trace } from "./Charts";
import { levelName, marketMove, numeric, percent, stamp } from "./format";
import { sourceList } from "./useReplay";

const statusIcons = {
  verified: ShieldCheck,
  developing: CircleDot,
  rumor: Radio,
  dismissed: Minus,
};
export function Badge({ level }) {
  const Icon = statusIcons[level] || CircleDot;
  return (
    <span className={`badge ${level}`}>
      <Icon size={12} />
      {levelName[level]}
    </span>
  );
}
export function Ticker({ children }) {
  return <span className="ticker">{children}</span>;
}
function highlight(text, item) {
  const terms = [item.company, item.ceo].filter((t) => text.includes(t));
  if (!terms.length || !item.matched) return text;
  return text
    .split(new RegExp(`(${terms.join("|")})`, "g"))
    .map((part, i) => (terms.includes(part) ? <em key={i}>{part}</em> : part));
}

export function Metrics({ frame }) {
  const sources = sourceList.length;
  const avg = frame.alerts.length
    ? frame.alerts.reduce((v, a) => v + a.latency, 0) / frame.alerts.length
    : null;
  let count = 0;
  const counts = frame.logs.map((l) => (count += l.count));
  const alertCounts = frame.items.map(
    (it) => frame.alerts.filter((a) => a.id <= it.id).length,
  );
  const cells = [
    {
      icon: RadioTower,
      label: "Sources online",
      value: sources,
      suffix: `/ ${sources}`,
      detail: "Demo channels",
      viz: "sources",
    },
    {
      icon: ScanLine,
      label: "Items scanned",
      value: numeric(frame.scanned),
      detail: `+${numeric(frame.batch)} in latest batch`,
      data: counts,
      color: "var(--mint)",
    },
    {
      icon: Activity,
      label: "Detection latency",
      value: avg === null ? "—" : avg.toFixed(1),
      suffix: "s",
      detail: "Average per alert",
      data: frame.items.map((i) => i.at - i.published),
      color: "#bdc8c1",
    },
    {
      icon: Bell,
      label: "Alerts today",
      value: String(frame.alerts.length).padStart(2, "0"),
      detail: `${frame.alerts.filter((a) => a.level === "verified").length} verified · ${frame.alerts.filter((a) => a.level === "developing").length} developing`,
      data: alertCounts,
      color: "var(--amber)",
      style: "bar",
    },
  ];
  return (
    <section className="metrics" aria-label="Scanner statistics">
      {cells.map((c) => (
        <div className="metric" key={c.label}>
          <div className="metric-label">
            <c.icon size={15} strokeWidth={1.65} />
            {c.label}
          </div>
          <div className="metric-mid">
            <div className="metric-value">
              {c.value}
              <small>{c.suffix}</small>
            </div>
            {c.viz === "sources" ? (
              <div className="source-bars" aria-hidden="true">
                {sourceList.map((s) => (
                  <i key={s[0]} />
                ))}
              </div>
            ) : (
              <Trace values={c.data} color={c.color} style={c.style} />
            )}
          </div>
          <p>{c.detail}</p>
        </div>
      ))}
    </section>
  );
}
export function Focus({ item, signal, frame, paused, onMarket }) {
  const evidence = useMemo(
    () => (signal ? signal.evidence.map((id) => frame.items[id]) : [item]),
    [signal, frame.items, item],
  );
  const move = signal && marketMove(signal.prices);
  return (
    <section className="panel focus-panel" aria-labelledby="focus-title">
      <div className="panel-title focus-label">
        <Crosshair size={16} />
        <h2 id="focus-title">Signal in focus</h2>
      </div>
      <div className="focus-field">
        <div className="focus-copy">
          <div className="focus-tags">
            <Ticker>{item.ticker}</Ticker>
            <Badge level={signal?.level || item.level} />
          </div>
          <h3>{item.title}</h3>
          <p>{item.text}</p>
        </div>
        <div className="scope-box">
          <Scope evidence={evidence} ticker={item.ticker} paused={paused} />
          <div className="scope-caption">
            <i />
            {String(evidence.length).padStart(2, "0")} SOURCE{" "}
            {evidence.length === 1 ? "RETURN" : "RETURNS"}
          </div>
        </div>
      </div>
      <div className="focus-footer">
        <div>
          <span>Subject</span>
          <strong>{item.matched ? item.ceo : "No CEO match"}</strong>
        </div>
        <div>
          <span>Detected at</span>
          <strong className="mono">
            {stamp(item.at)} <small>UTC</small>
          </strong>
        </div>
        <div>
          <span>Market reaction</span>
          {signal ? (
            <button
              className={`market-link ${move < 0 ? "negative" : "positive"}`}
              onClick={onMarket}
              aria-label="View simulated market reaction"
            >
              {percent(move)}
              <Activity size={14} />
            </button>
          ) : (
            <strong>—</strong>
          )}
        </div>
      </div>
    </section>
  );
}
export function Feed({
  frame,
  item,
  onSelect,
  paused,
  ended,
  command,
  connected,
}) {
  const [filter, setFilter] = useState("All items");
  const [newest, setNewest] = useState(true);
  const items = frame.items.filter(
    (r) =>
      filter === "All items" || (filter === "Matched" ? r.matched : !r.matched),
  );
  const sorted = newest ? [...items].reverse() : items;
  return (
    <section className="panel feed-panel" aria-labelledby="feed-title">
      <div className="section-head">
        <div className="panel-title">
          <Waves size={17} />
          <h2 id="feed-title">Live feed</h2>
        </div>
        <span
          className={`live-state ${paused || ended || !connected ? "idle" : ""}`}
        >
          <i />
          {!connected
            ? "Connecting"
            : ended
              ? "Complete"
              : paused
                ? "Paused"
                : "Streaming"}
        </span>
      </div>
      <div className="feed-controls">
        <div className="filter-pills" aria-label="Filter headlines">
          {["All items", "Matched", "Dismissed"].map((f) => (
            <button
              className={filter === f ? "current" : ""}
              aria-pressed={filter === f}
              key={f}
              onClick={() => setFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
        <button
          className={`bare-icon ${newest ? "" : "mint"}`}
          onClick={() => setNewest(!newest)}
          title={
            newest
              ? "Newest first · switch to oldest first"
              : "Oldest first · switch to newest first"
          }
          aria-label={
            newest ? "Change to oldest first" : "Change to newest first"
          }
        >
          <ListFilter size={16} />
        </button>
      </div>
      <div
        className="feed-scroll"
        tabIndex="0"
        aria-label="Scrollable headlines"
      >
        {sorted.length ? (
          sorted.map((r) => (
            <button
              key={r.id}
              className={`feed-row ${item.id === r.id ? "chosen" : ""} ${r.matched && r.kind !== "filing" ? "relationship-row" : ""}`}
              aria-pressed={item.id === r.id}
              onClick={() => onSelect(r)}
            >
              <div className="row-meta">
                <span className={`dot ${r.level}`} />
                <span>{r.publisher}</span>
                <time>{stamp(r.at)}</time>
              </div>
              <h3>{highlight(r.title, r)}</h3>
              <div className="row-tags">
                <Ticker>{r.ticker}</Ticker>
                <span className={`text-status ${r.level}`}>
                  {levelName[r.level]}
                </span>
              </div>
            </button>
          ))
        ) : (
          <p className="empty">
            No {filter.toLowerCase()} items in this replay yet.
          </p>
        )}
      </div>
      <div className="feed-footer">
        <span>
          {items.length} {items.length === 1 ? "item" : "items"} ·{" "}
          {newest ? "Newest" : "Oldest"} first
        </span>
        <button
          disabled={!connected}
          onClick={() => command(ended ? "replay" : "pause")}
        >
          {ended || paused ? <Play size={12} /> : <Pause size={12} />}{" "}
          {ended ? "Replay" : paused ? "Resume" : "Pause"}
        </button>
      </div>
    </section>
  );
}
export function Analysis({ item, signal, frame, tab, setTab, inspect }) {
  const confidence = signal?.confidence ?? item.confidence;
  return (
    <section className="panel analysis-panel">
      <div className="analysis-head">
        <div className="panel-title">
          <SlidersHorizontal size={16} />
          <h2>Signal analysis</h2>
        </div>
        <div className="analysis-tabs" aria-label="Analysis view">
          {["Classifier", "Verification", "Market"].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              aria-pressed={tab === t}
              className={tab === t ? "current" : ""}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      {tab === "Classifier" ? (
        <div className="analysis-body">
          <div className="confidence-heading">
            <span>Classifier confidence</span>
            <b>
              {confidence}
              <small>%</small>
            </b>
          </div>
          <div className="confidence-track">
            <motion.div
              key={item.id}
              initial={{ width: 0 }}
              animate={{ width: `${confidence}%` }}
              transition={{ duration: 0.55 }}
            />
          </div>
          <div className="analysis-foot">
            <span>
              {item.matched ? <CheckCheck size={15} /> : <Minus size={15} />}{" "}
              {item.matched
                ? "CEO and company matched"
                : "Routine coverage dismissed"}
            </span>
            <span className="mono">Demo rules</span>
          </div>
        </div>
      ) : tab === "Verification" ? (
        <div className="evidence-list">
          {signal ? (
            signal.evidence.map((id) => (
              <button key={id} onClick={() => inspect(frame.items[id])}>
                <CircleCheck size={14} />
                <strong>{frame.items[id].publisher}</strong>
                <span>
                  {frame.items[id].kind === "filing"
                    ? "Departure filing"
                    : frame.items[id].kind === "social"
                      ? "Social post"
                      : "Report"}
                </span>
                <ChevronRight size={13} />
              </button>
            ))
          ) : (
            <p className="empty">
              No evidence to verify for this dismissed item.
            </p>
          )}
        </div>
      ) : (
        <div className="market-view">
          {signal ? (
            <>
              <div>
                <span>Since first detection</span>
                <strong
                  className={
                    marketMove(signal.prices) < 0 ? "negative" : "positive"
                  }
                >
                  {percent(marketMove(signal.prices))}
                </strong>
                <small>Simulated prices · USD</small>
              </div>
              <div className="market-plot">
                <Trace
                  large
                  values={signal.prices}
                  color={
                    marketMove(signal.prices) < 0
                      ? "var(--coral)"
                      : "var(--mint)"
                  }
                />
                <div>
                  <small>${signal.prices[0].toFixed(2)}</small>
                  <small>${signal.prices.at(-1).toFixed(2)}</small>
                </div>
              </div>
            </>
          ) : (
            <p className="empty">
              Market context starts when a signal is detected.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
export function Terminal({ frame, expanded, setExpanded }) {
  const logs = [...frame.logs].reverse();
  const rate =
    frame.items.length > 1
      ? (frame.scanned - frame.logs[0].count) / (frame.at - frame.logs[0].at)
      : 0;
  return (
    <section className="panel terminal">
      <div className="section-head">
        <div className="panel-title">
          <TerminalSquare size={16} />
          <h2>Scanner terminal</h2>
        </div>
        <div className="terminal-actions">
          <span>{rate.toFixed(1)} items/s</span>
          <button
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "Collapse" : "Expand"}
          </button>
        </div>
      </div>
      <div className="terminal-lines">
        {logs.slice(0, expanded ? logs.length : 3).map((l) => (
          <div key={l.at}>
            <time>{stamp(l.at)}</time>
            <b>{l.source}</b>
            <span>
              {l.message} <em>· {numeric(l.count)} scanned</em>
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
