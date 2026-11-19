import { newMatchTracker, newReportMatches } from "./matchAlerts";
import React, { useState, useEffect, useRef } from "react";
import { ExternalLink, Search, ChevronRight } from "lucide-react";
import { numeric, stamp } from "./format";

export const functions = [
  ["MON", "Monitor"],
  ["NWS", "Headlines"],
  ["MTCH", "Review queue"],
  ["FIL", "Filings"],
  ["SRC", "Sources"],
  ["DIR", "Directory"],
];
const tag = { wire: "WIRE", candidate: "MATCH", filing: "8-K" };
const states = {
  online: "Online",
  starting: "Starting",
  degraded: "Partial",
  error: "Offline",
  backoff: "Backoff",
  disabled: "Disabled",
  waiting: "Waiting",
  gap: "Gap",
};
const age = (at, now) =>
  !at
    ? "—"
    : now - at < 60
      ? `${Math.max(0, now - at)}s`
      : now - at < 3600
        ? `${Math.floor((now - at) / 60)}m`
        : `${Math.floor((now - at) / 3600)}h`;
const displayDate = (t) =>
  t
    ? new Date(t * 1000).toISOString().slice(0, 16).replace("T", " ") + " UTC"
    : "—";
const sourceName = (r, sourceMap) => sourceMap[r.source]?.name || r.publisher;
function Pane({ code, title, side, children, className = "" }) {
  return (
    <section className={"term-pane " + className}>
      <header className="pane-bar">
        <h2>
          <b>{code}</b>
          {title}
        </h2>
        {side}
      </header>
      {children}
    </section>
  );
}
function Empty({ children }) {
  return <div className="term-empty">{children}</div>;
}
function Stats({ data, now, stale }) {
  const ok = data.sources.filter((s) => s.state === "online").length,
    enabled = data.sources.filter((s) => s.state !== "disabled").length;
  return (
    <div className="term-stats">
      {[
        [numeric(data.scanned), "Records scanned", "Since 00:00 UTC", "amber"],
        [
          numeric(data.counts.candidate || 0),
          "Review matches",
          "CEO + issuer",
          "cyan",
        ],
        [
          numeric(data.counts.filing || 0),
          "Item 5.02 filings",
          "Rolling window",
          "cyan",
        ],
        [
          ok + " / " + enabled,
          "Sources online",
          stale ? "At last update" : "Enabled channels",
          "green",
        ],
        [
          numeric(data.directory.securities),
          "S&P securities",
          numeric(data.directory.covered) + " with CEO names",
          "white",
        ],
      ].map(([v, label, detail, color]) => (
        <div key={label}>
          <span>{label}</span>
          <strong className={stale ? "white" : color}>{v}</strong>
          <small>{detail}</small>
        </div>
      ))}
    </div>
  );
}
function Activity({ data }) {
  const [hover, setHover] = useState(null),
    [mode, setMode] = useState("Published");
  const wire = mode === "Published" && data.publications;
  const bins = wire ? data.publications : data.activity,
    start = wire ? data.publication_start : data.activity_start,
    step = wire ? data.publication_step : 60;
  const max = Math.max(1, ...bins),
    picked = hover != null && hover < bins.length ? hover : bins.length - 1;
  return (
    <Pane
      code="ACT"
      title="Wire activity"
      className="activity-pane"
      side={<small>{step / 60} MIN BARS</small>}
    >
      <div className="activity-caption">
        <div className="chart-switch">
          {["Published", "Scanned"].map((m) => (
            <button
              key={m}
              aria-pressed={m === mode}
              onClick={() => {
                setMode(m);
                setHover(null);
              }}
            >
              {m}
            </button>
          ))}
        </div>
        <b>
          {numeric(bins[picked])}
          <small> / {step / 60}m</small>
        </b>
      </div>
      <div className="plot">
        <div className="plot-y">
          <span>{max}</span>
          <span>0</span>
        </div>
        <div
          className="bars"
          role="img"
          aria-label={mode + " records. Peak " + max + " per interval."}
          onMouseLeave={() => setHover(null)}
        >
          {bins.map((n, i) => (
            <div
              key={i}
              onMouseEnter={() => setHover(i)}
              title={
                stamp(start + i * step, true) +
                " UTC · " +
                numeric(n) +
                " records"
              }
            >
              <i style={{ height: (100 * n) / max + "%" }} />
            </div>
          ))}
        </div>
      </div>
      <div className="plot-x">
        <span>{stamp(start, true)}</span>
        <span>{stamp(start + Math.floor(bins.length / 2) * step, true)}</span>
        <span>{stamp(start + (bins.length - 1) * step, true)} UTC</span>
      </div>
    </Pane>
  );
}
function FeedTable({ rows, sourceMap, selected, choose, limit }) {
  if (!rows.length) return <Empty>No records in the current window.</Empty>;
  return (
    <div className="term-table-scroll">
      <table className="news-table">
        <thead>
          <tr>
            <th>Time UTC</th>
            <th>Headline</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, limit).map((r) => (
            <tr
              key={r.id}
              className={`${selected?.id === r.id ? "selected" : ""} ${r.kind === "candidate" ? "relationship-row" : ""}`}
            >
              <td className="tabular">{stamp(r.published_at, true)}</td>
              <td>
                <button
                  className="headline-action"
                  onClick={() => choose(r)}
                  aria-pressed={selected?.id === r.id}
                >
                  {r.kind === "candidate" && (
                    <span className="relationship-tag">MATCH</span>
                  )}
                  {r.ticker && <b>{r.ticker} </b>}
                  {r.title}
                </button>
              </td>
              <td title={sourceName(r, sourceMap)}>
                {sourceName(r, sourceMap)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Reader({ r, sourceMap }) {
  return (
    <Pane
      code="RDR"
      title="Story detail"
      className={
        r?.kind === "candidate"
          ? "reader-pane relationship-reader"
          : "reader-pane"
      }
      side={<small>{r ? tag[r.kind] || "WIRE" : "—"}</small>}
    >
      {r ? (
        <article className="reader">
          <div className="reader-meta">
            {sourceName(r, sourceMap)}
            <i /> {stamp(r.published_at)} UTC{" "}
            {r.basis === "first_seen" ? "· First seen" : ""}
          </div>
          <h3>{r.title}</h3>
          {r.text && r.text !== r.title && <p>{r.text}</p>}
          {r.kind === "candidate" && (
            <p className="review-note">
              Entity match for {r.ceo} and {r.company} ({r.ticker}). Awaiting
              claim review.
            </p>
          )}
          {r.kind === "filing" && (
            <p className="review-note">
              Issuer filing · Item 5.02 can include appointments, departures or
              compensation.
            </p>
          )}
          <div className="evidence-links">
            {r.evidence.map((e, i) => (
              <a
                key={e.url + e.source}
                href={e.url}
                target="_blank"
                rel="noreferrer"
              >
                {r.evidence.length === 1 ? "Open source" : e.publisher}
                <ExternalLink size={12} />
              </a>
            ))}
          </div>
        </article>
      ) : (
        <Empty>Select a headline or filing to read its source record.</Empty>
      )}
    </Pane>
  );
}
function Sources({ data, now, detail = false, open }) {
  return (
    <Pane
      code="SRC"
      title="Source monitor"
      className="source-pane"
      side={
        !detail && (
          <button onClick={open}>
            Details <ChevronRight size={12} />
          </button>
        )
      }
    >
      <div className="term-table-scroll">
        <table className="source-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>State</th>
              <th>Last check</th>
              {detail && (
                <>
                  <th>Items scanned</th>
                  <th>Last result</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {data.sources.map((s) => (
              <tr key={s.key}>
                <td>{s.name}</td>
                <td>
                  <span className={"source-state " + s.state}>
                    <i />
                    {states[s.state] || s.state}
                  </span>
                </td>
                <td className="tabular" title={displayDate(s.last_at)}>
                  {age(s.last_at, now)}
                </td>
                {detail && (
                  <>
                    <td>{numeric(s.scanned)}</td>
                    <td>
                      {s.error ||
                        (s.last_ok
                          ? `${s.added} new records`
                          : "Awaiting response")}
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Pane>
  );
}
function DirectoryView({ directory, query, setQuery }) {
  const [cap, setCap] = useState(50);
  if (!directory) return <Empty>Loading the constituent directory…</Empty>;
  const q = query.trim().toLowerCase(),
    rows = directory.companies.filter((c) =>
      [
        c.ticker,
        c.company,
        c.sector,
        ...c.ceos.flatMap((p) => [p.name, ...(p.aliases || [])]),
      ]
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
  return (
    <Pane
      code="DIR"
      title="S&P 500 constituent directory"
      side={<small>{rows.length} SECURITIES</small>}
    >
      <div className="term-tools">
        <label>
          <Search size={14} />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setCap(50);
            }}
            placeholder="Ticker, issuer, sector or CEO"
            aria-label="Filter constituent directory"
          />
        </label>
        <span>As of {directory.fetched_at.slice(0, 10)}</span>
      </div>
      <div className="term-table-scroll">
        <table className="dir-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Company</th>
              <th>Chief executive</th>
              <th>Sector</th>
              <th>CIK</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, cap).map((c) => (
              <tr key={c.ticker}>
                <td className="cyan">{c.ticker}</td>
                <td>{c.company}</td>
                <td>
                  {c.ceos.length ? (
                    c.ceos.map((p, i) => (
                      <React.Fragment key={p.name}>
                        {i > 0 ? ", " : ""}
                        {/^https?:\/\//.test(p.source) ? (
                          <a href={p.source} target="_blank" rel="noreferrer">
                            {p.name}
                          </a>
                        ) : (
                          p.name
                        )}
                      </React.Fragment>
                    ))
                  ) : (
                    <span className="muted">Unresolved</span>
                  )}
                </td>
                <td>{c.sector}</td>
                <td className="tabular">{c.cik}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && <Empty>No constituents match this search.</Empty>}
      {rows.length > cap && (
        <button className="load-more" onClick={() => setCap(cap + 100)}>
          Show more constituents
        </button>
      )}
    </Pane>
  );
}
function Filings({ rows, choose, open }) {
  return (
    <Pane
      code="FIL"
      title="Executive filings"
      side={
        <button onClick={open}>
          Item 5.02 <ChevronRight size={12} />
        </button>
      }
    >
      {rows.length ? (
        <div className="filing-list">
          {rows.slice(0, 3).map((r) => (
            <button key={r.id} onClick={() => choose(r)}>
              <b>{r.ticker}</b>
              <span>{r.company}</span>
              <time>{stamp(r.published_at, true)}</time>
            </button>
          ))}
        </div>
      ) : (
        <Empty>No new Item 5.02 filings in the scan window.</Empty>
      )}
    </Pane>
  );
}
export default function LiveDesk({
  data,
  playAlert,
  error,
  directory,
  page,
  setPage,
  query,
  setQuery,
  now,
}) {
  const [selection, setSelection] = useState(null),
    [filter, setFilter] = useState("All"),
    [search, setSearch] = useState("");
  const tracker = useRef(null);
  const [announcement, setAnnouncement] = useState(null);
  useEffect(() => {
    tracker.current ??= newMatchTracker();
    const arrivals = newReportMatches(
      data,
      tracker.current,
      Math.floor(Date.now() / 1000),
    );
    if (arrivals.length) {
      setAnnouncement({ id: arrivals[0].id, count: arrivals.length });
      playAlert();
    }
  }, [data, playAlert]);
  if (!data)
    return (
      <div className="term-loading">
        <h1>Executive monitor</h1>
        <p>{error || "Connecting to collector…"}</p>
      </div>
    );
  const stale = now - data.as_of > 75 || Boolean(error),
    cutoff = now - data.window_seconds;
  const rows = data.records.filter((r) => r.published_at >= cutoff);
  const latestMatch =
    announcement &&
    rows.find((r) => r.id === announcement.id && r.kind === "candidate");
  const sourceMap = Object.fromEntries(data.sources.map((s) => [s.key, s]));
  const select = (r) => {
    setSelection(r.id);
    requestAnimationFrame(() => {
      const el = document.querySelector(".reader-pane");
      if (
        el &&
        (el.getBoundingClientRect().top > innerHeight * 0.85 ||
          el.getBoundingClientRect().bottom < 0)
      )
        el.scrollIntoView({ block: "center" });
    });
  };
  const pageRows = rows.filter((r) =>
    page === "FIL"
      ? r.kind === "filing"
      : page === "MTCH"
        ? r.kind === "candidate"
        : true,
  );
  const list =
    page === "MON"
      ? pageRows.filter(
          (r) =>
            filter === "All" ||
            r.kind === (filter === "Matches" ? "candidate" : "filing"),
        )
      : pageRows.filter((r) =>
          (r.title + r.ticker + r.company + r.publisher)
            .toLowerCase()
            .includes(search.toLowerCase()),
        );
  const selected =
    rows.find((r) => r.id === selection && list.some((i) => i.id === r.id)) ||
    list[0];
  const title = {
    MON: "Executive monitor",
    NWS: "Headline wire",
    MTCH: "Review queue",
    FIL: "Executive filings",
    SRC: "Source status",
    DIR: "Company directory",
  }[page];
  const filings = rows.filter((r) => r.kind === "filing");
  return (
    <main className="terminal-main">
      {latestMatch && (
        <aside
          className="relationship-banner"
          aria-label="Relationship news alert"
        >
          <div role="status" aria-live="polite" aria-atomic="true">
            <strong>
              {announcement.count === 1
                ? "New relationship match"
                : announcement.count + " new relationship matches"}{" "}
              · Awaiting review
            </strong>
            <span>
              {latestMatch.ticker} · {latestMatch.title}
            </span>
          </div>
          <button
            onClick={() => {
              setSearch("");
              setPage("MTCH");
              select(latestMatch);
              setAnnouncement(null);
            }}
          >
            Review
          </button>
          <button
            aria-label="Dismiss match alert"
            onClick={() => setAnnouncement(null)}
          >
            ×
          </button>
        </aside>
      )}
      <div className="workspace-heading">
        <div>
          <div className="function-path">
            US EQUITIES <span>/</span> EXECUTIVE INTELLIGENCE
          </div>
          <h1>{title}</h1>
        </div>
        <div className="asof">
          <span className={stale ? "stream-state amber" : "stream-state green"}>
            <i />
            {stale ? "STALE FEED" : "COLLECTOR ONLINE"}
          </span>
          <span>Last update {stamp(data.as_of)} UTC</span>
        </div>
      </div>
      {stale && (
        <div className="stale-banner">
          {error || "Collector heartbeat overdue"}. Last snapshot{" "}
          {displayDate(data.as_of)}.
        </div>
      )}
      {page === "MON" ? (
        <>
          <Stats data={data} now={now} stale={stale} />
          <div className="monitor-grid">
            <div className="wire-column">
              <Pane
                code="NWS"
                title="Headline wire"
                side={
                  <button onClick={() => setPage("NWS")}>
                    All headlines <ChevronRight size={12} />
                  </button>
                }
              >
                <div className="wire-tools">
                  <div>
                    {["All", "Matches", "Filings"].map((f) => (
                      <button
                        aria-pressed={filter === f}
                        className={filter === f ? "on" : ""}
                        key={f}
                        onClick={() => setFilter(f)}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                  <small>LAST {Math.round(data.window_seconds / 3600)}H</small>
                </div>
                <FeedTable
                  {...{ sourceMap, selected, choose: select }}
                  rows={list}
                  limit={10}
                />
              </Pane>
              <Reader r={selected} sourceMap={sourceMap} />
            </div>
            <aside className="instrument-column">
              <Activity data={data} />
              <Sources {...{ data, now }} open={() => setPage("SRC")} />
              <Filings
                rows={filings}
                choose={(r) => {
                  setFilter("Filings");
                  select(r);
                }}
                open={() => setPage("FIL")}
              />
            </aside>
          </div>
        </>
      ) : page === "SRC" ? (
        <Sources {...{ data, now }} detail />
      ) : page === "DIR" ? (
        <DirectoryView {...{ directory, query, setQuery }} />
      ) : (
        <div className="sub-grid">
          <Pane
            code={page}
            title={
              page === "NWS"
                ? "All headlines"
                : page === "FIL"
                  ? "SEC Item 5.02"
                  : "Entity matches awaiting review"
            }
            side={<small>{list.length} RECORDS</small>}
          >
            <div className="term-tools">
              <label>
                <Search size={14} />
                <input
                  aria-label="Filter records"
                  placeholder="Filter records"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
            </div>
            <FeedTable
              {...{ sourceMap, selected, choose: select }}
              rows={list}
              limit={200}
            />
          </Pane>
          <Reader r={selected} sourceMap={sourceMap} />
        </div>
      )}
      <footer className="term-footer">
        <span>
          SR TERMINAL <i /> {data.directory.issuers} issuers
        </span>
        <span>Times in UTC · Window {data.window_seconds / 3600}h</span>
      </footer>
    </main>
  );
}
