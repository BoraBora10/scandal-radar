import React, { useEffect, useRef, useState } from "react";

import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import {
  ChevronDown,
  ChevronRight,
  Clock3,
  FileText,
  FlaskConical,
  Layers3,
  Newspaper,
  Radio,
  RadioTower,
  RotateCcw,
  Search,
  X,
} from "lucide-react";
import "@fontsource-variable/geist/index.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "./styles.css";
import {
  Analysis,
  Badge,
  Feed,
  Focus,
  Metrics,
  Terminal,
  Ticker,
} from "./Panels";
import { Trace } from "./Charts";
import { sourceList, useReplay } from "./useReplay";
import { marketMove, percent, stamp } from "./format";

const dateLabel = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  month: "long",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
}).format(new Date());
const pages = ["Overview", "Alerts", "Sources"];
const sourceIcons = [Newspaper, RadioTower, FileText, Radio, Layers3, Search];

function Header({ page, go, frame }) {
  return (
    <header className="topbar">
      <div className="shell topbar-inner">
        <button
          className="brand"
          onClick={() => go("Overview")}
          aria-label="Scandal Radar overview"
        >
          <img src="/radar.svg" alt="" />
          <span>Scandal Radar</span>
        </button>
        <nav aria-label="Primary">
          {pages.map((p) => (
            <button
              key={p}
              aria-current={p === page ? "page" : undefined}
              className={p === page ? "active" : ""}
              onClick={() => go(p)}
            >
              {p}
              {p === "Alerts" && <small>{frame.alerts.length}</small>}
            </button>
          ))}
        </nav>
        <div className="head-right">
          <span className="session-time" title="Simulated session time">
            <Clock3 size={13} />
            {stamp(frame.at)} <span>UTC</span>
          </span>
        </div>
      </div>
    </header>
  );
}
function Archive({ frame, open }) {
  const [query, setQuery] = useState(""),
    [level, setLevel] = useState("all");
  const results = [...frame.alerts]
    .reverse()
    .filter(
      (a) =>
        (level === "all" || a.level === level) &&
        (a.title + a.ticker + frame.items[a.id].ceo)
          .toLowerCase()
          .includes(query.toLowerCase()),
    );
  return (
    <section className="panel archive">
      <div className="archive-controls">
        <label className="search">
          <Search size={16} />
          <input
            aria-label="Search alerts"
            placeholder="Search alerts"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label className="select-wrap">
          <select
            aria-label="Verification level"
            value={level}
            onChange={(e) => setLevel(e.target.value)}
          >
            <option value="all">All levels</option>
            <option value="verified">Verified</option>
            <option value="developing">Developing</option>
          </select>
          <ChevronDown size={12} />
        </label>
      </div>
      {results.length ? (
        results.map((a) => {
          const item = frame.items[a.id],
            prices = frame.signals[a.ticker].prices;
          return (
            <button
              className="archive-row"
              key={a.id}
              onClick={() => open(item)}
            >
              <div className="archive-time">
                <time>{stamp(a.at)}</time>
                <small>{a.update ? "Level update" : "Detection"}</small>
              </div>
              <div className="archive-copy">
                <div>
                  <Ticker>{a.ticker}</Ticker>
                  <Badge level={a.level} />
                </div>
                <h3>{a.title}</h3>
                <p>
                  {item.ceo} · {item.publisher} · {a.latency}s latency
                </p>
              </div>
              <div className="archive-market">
                <Trace
                  values={prices}
                  color={
                    marketMove(prices) < 0 ? "var(--coral)" : "var(--mint)"
                  }
                />
                <small>{percent(marketMove(prices))} · simulated</small>
              </div>
              <ChevronRight size={16} />
            </button>
          );
        })
      ) : (
        <p className="empty">No alerts match this view.</p>
      )}
    </section>
  );
}
function Sources({ frame, inspect }) {
  return (
    <section className="panel sources">
      <div className="section-head">
        <div className="panel-title">
          <RadioTower size={16} />
          <h2>Source directory</h2>
        </div>
        <span className="count-label">{sourceList.length} channels</span>
      </div>
      {sourceList.map(([name, desc, transport], i) => {
        const records = frame.items.filter((it) => it.source === i),
          last = records.at(-1),
          Icon = sourceIcons[i];
        return (
          <div className="source-row" key={name}>
            <div className="source-icon">
              <Icon size={19} />
            </div>
            <div className="source-desc">
              <strong>{name}</strong>
              <p>{desc}</p>
            </div>
            <span className="protocol">{transport}</span>
            <div className="source-read">
              <span>Last seen</span>
              <time>{last ? stamp(last.at) : "Awaiting record"}</time>
            </div>
            <button
              className="outline-btn small"
              disabled={!last}
              onClick={() => inspect(last)}
            >
              Latest item
            </button>
          </div>
        );
      })}
    </section>
  );
}
function EvidenceDialog({ item, onClose }) {
  const dialog = useRef(null);
  useEffect(() => {
    const el = dialog.current;
    el.showModal();
    return () => el.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === dialog.current) onClose();
      }}
      className="evidence-dialog"
      aria-label="Source record"
    >
      <div className="dialog-head">
        <span className="panel-title">
          <FileText size={16} />
          Source record
        </span>
        <button
          className="bare-icon"
          onClick={onClose}
          aria-label="Close source record"
        >
          <X size={18} />
        </button>
      </div>
      <div className="dialog-copy">
        <div className="focus-tags">
          <Ticker>{item.ticker}</Ticker>
          <span className="sim-tag">Simulated</span>
        </div>
        <h2>{item.title}</h2>
        <p>{item.text}</p>
        <dl>
          <div>
            <dt>Publisher</dt>
            <dd>{item.publisher}</dd>
          </div>
          <div>
            <dt>Channel</dt>
            <dd>{sourceList[item.source][0]}</dd>
          </div>
          <div>
            <dt>Published</dt>
            <dd>{stamp(item.published)} UTC</dd>
          </div>
          <div>
            <dt>Detected</dt>
            <dd>{stamp(item.at)} UTC</dd>
          </div>
        </dl>
      </div>
    </dialog>
  );
}
function AlertTakeover({ alert, onClose, inspect }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    el.showModal();
    return () => el.close();
  }, []);
  return (
    <motion.dialog
      ref={ref}
      onCancel={onClose}
      className="takeover"
      aria-label="Simulated alert"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <div className="takeover-card">
        <div className="takeover-top">
          <span className="sim-tag">
            <FlaskConical size={12} /> Simulated
          </span>
          <button
            onClick={onClose}
            className="bare-icon"
            aria-label="Dismiss alert"
          >
            <X size={18} />
          </button>
        </div>
        <div className="takeover-signal">
          <RadioTower size={34} />
        </div>
        <Badge level={alert.level} />
        <h2>
          {alert.update ? "Verification updated" : "Scandal detected"}
          <br />
          <span>${alert.ticker}</span>
        </h2>
        <p>{alert.title}</p>
        <div className="takeover-meta">
          {stamp(alert.at)} UTC · {alert.latency}s latency
        </div>
        <button className="primary-btn" onClick={inspect}>
          Inspect signal
          <ChevronRight size={15} />
        </button>
      </div>
    </motion.dialog>
  );
}
export default function ReplayDesk({ playAlert }) {
  const { frame, speed, paused, ended, command, connected, index } =
    useReplay();
  const [page, setPage] = useState("Overview"),
    [selected, setSelected] = useState(9),
    [tab, setTab] = useState("Classifier"),
    [expanded, setExpanded] = useState(false);
  const [evidence, setEvidence] = useState(null),
    [alert, setAlert] = useState(null);
  const seen = useRef({ index, alerts: frame.alerts.length });
  const item = frame.items.find((r) => r.id === selected) || frame.items.at(-1);
  const signal = item.matched ? frame.signals[item.ticker] : null;
  const go = (p) => {
    setPage(p);
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  function reveal(selector) {
    requestAnimationFrame(() => {
      const panel = document.querySelector(selector);
      if (!panel) return;
      const box = panel.getBoundingClientRect();
      if (box.bottom < 100 || box.top < -30 || box.top > innerHeight - 80)
        panel.scrollIntoView({ block: "start", behavior: "instant" });
    });
  }
  function openItem(it) {
    setSelected(it.id);
    setTab("Classifier");
    if (page !== "Overview") go("Overview");
    else reveal(".focus-slot");
  }
  function showMarket() {
    setTab("Market");
    reveal(".analysis-slot");
  }
  useEffect(() => {
    const prev = seen.current;
    seen.current = { index, alerts: frame.alerts.length };
    if (index <= prev.index || frame.alerts.length <= prev.alerts) return;
    const next = frame.alerts.at(-1);
    setAlert(next);
    setSelected(next.id);
    playAlert();
  }, [index, frame.alerts, playAlert]);
  useEffect(() => {
    if (!alert) return;
    const id = setTimeout(() => setAlert(null), 3400);
    return () => clearTimeout(id);
  }, [alert]);
  function replay() {
    setAlert(null);
    setEvidence(null);
    setSelected(-1);
    setTab("Classifier");
    command("replay");
  }
  const activeTitle =
    page === "Overview"
      ? "Monitoring desk"
      : page === "Alerts"
        ? "Alert archive"
        : "Sources";
  return (
    <MotionConfig reducedMotion="user">
      <Header {...{ page, go, frame }} />
      <main className="shell main-shell">
        <section className="page-heading">
          <div>
            <div className="title-line">
              <h1>{activeTitle}</h1>
              <span className="sim-tag">
                <FlaskConical size={12} />
                Simulated
              </span>
            </div>
            <p className="date-line">{dateLabel}</p>
          </div>
          <div className="playback">
            <label className="select-wrap speed">
              <select
                aria-label="Replay speed"
                disabled={!connected}
                value={speed}
                onChange={(e) => command("speed", Number(e.target.value))}
              >
                {[0.5, 1, 2, 4].map((s) => (
                  <option key={s} value={s}>
                    {s}×
                  </option>
                ))}
              </select>
              <ChevronDown size={12} />
            </label>
            <button
              className="primary-btn"
              disabled={!connected}
              onClick={replay}
            >
              <RotateCcw size={14} />
              Replay demo
            </button>
          </div>
        </section>
        {page === "Overview" ? (
          <>
            <Metrics frame={frame} />
            <div className="desk-grid">
              <div className="focus-slot">
                <Focus
                  {...{ item, signal, frame, paused: paused || ended }}
                  onMarket={showMarket}
                />
              </div>
              <div className="feed-slot">
                <Feed
                  {...{ frame, item, paused, ended, command, connected }}
                  onSelect={openItem}
                />
              </div>
              <div className="analysis-slot">
                <Analysis
                  {...{ item, signal, frame, tab, setTab }}
                  inspect={setEvidence}
                />
              </div>
            </div>
            <Terminal {...{ frame, expanded, setExpanded }} />
          </>
        ) : page === "Alerts" ? (
          <Archive frame={frame} open={openItem} />
        ) : (
          <Sources frame={frame} inspect={setEvidence} />
        )}
        <footer className="footnote">
          <span>
            <span className="footer-square" />
            Scandal Radar
          </span>
          <span>Fictional replay · All times UTC</span>
        </footer>
      </main>
      {evidence && (
        <EvidenceDialog item={evidence} onClose={() => setEvidence(null)} />
      )}
      <AnimatePresence>
        {alert && (
          <AlertTakeover
            key={alert.id}
            alert={alert}
            onClose={() => setAlert(null)}
            inspect={() => {
              openItem(frame.items[alert.id]);
              setAlert(null);
            }}
          />
        )}
      </AnimatePresence>
    </MotionConfig>
  );
}
