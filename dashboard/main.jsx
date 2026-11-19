import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  CornerDownLeft,
  SquareTerminal,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import ReplayDesk from "./ReplayDesk";
import LiveDesk, { functions } from "./LiveDesk";
import { useLive } from "./useLive";
import { stamp } from "./format";
import { useAlertSound } from "./useAlertSound";
import "./terminal.css";

function Terminal() {
  const demoOnly =
    document.querySelector('meta[name="radar-mode"]')?.content === "demo";
  const [mode, setMode] = useState(demoOnly ? "demo" : "live"),
    [page, setPage] = useState("MON"),
    [query, setQuery] = useState("");
  const [input, setInput] = useState(""),
    [help, setHelp] = useState(false),
    [notice, setNotice] = useState(""),
    [now, setNow] = useState(Math.floor(Date.now() / 1000));
  const field = useRef(null);
  const sound = useAlertSound();
  const { snapshot, error, directory } = useLive(!demoOnly);
  useEffect(() => {
    let id = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 1000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    function key(e) {
      if (e.key === "Escape") {
        setHelp(false);
        setNotice("");
        field.current?.blur();
      }
      if (
        e.key === "/" &&
        !e.ctrlKey &&
        !e.metaKey &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(
          document.activeElement?.tagName,
        )
      ) {
        e.preventDefault();
        field.current.focus();
      }
    }
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, []);
  function openFunction(code) {
    if (demoOnly) {
      setNotice(
        "This instance is configured for replay. Start with DEMO_MODE=false for the live desk.",
      );
      return;
    }
    setMode("live");
    setPage(code);
    setHelp(false);
    setNotice("");
    setQuery("");
  }
  function submit(e) {
    e.preventDefault();
    const cmd = input.trim().toUpperCase();
    if (!cmd) {
      setHelp(true);
      return;
    }
    if (cmd === "HELP" || cmd === "?") {
      setHelp(true);
      setInput("");
      return;
    }
    if (["DEMO", "REPLAY"].includes(cmd)) {
      setMode("demo");
      setHelp(false);
      setNotice("");
    } else {
      const func = functions.find(
        ([c, n]) => c === cmd || n.toUpperCase() === cmd,
      );
      if (func) openFunction(func[0]);
      else if (directory?.companies.some((c) => c.ticker === cmd)) {
        openFunction("DIR");
        setQuery(cmd);
      } else {
        setNotice(
          "Unknown function or ticker. Enter HELP for available commands.",
        );
        return;
      }
    }
    setInput("");
    field.current?.blur();
  }
  return (
    <div className="radar-terminal">
      <header className="terminal-head">
        <button
          className="terminal-brand"
          onClick={() => (demoOnly ? setMode("demo") : openFunction("MON"))}
          aria-label="Scandal Radar terminal home"
        >
          <SquareTerminal size={24} strokeWidth={2.2} />
          <strong>Scandal Radar</strong>
        </button>
        <span className="product-name">TERMINAL</span>
        <div className="terminal-clock">
          <span>{new Date(now * 1000).toISOString().slice(0, 10)}</span>
          <b>{stamp(now)}</b> UTC
        </div>
        <button
          type="button"
          data-alert-sound
          className="alert-sound-control"
          onClick={sound.toggle}
          aria-pressed={sound.ready}
          disabled={!sound.supported}
          title={
            sound.ready
              ? "Mute the alert chime"
              : "Enable and preview the alert chime"
          }
        >
          {sound.ready ? <Volume2 size={15} /> : <VolumeX size={15} />}
          {sound.ready
            ? "Sound on"
            : !sound.supported
              ? "Audio unavailable"
              : sound.failed
                ? "Retry sound"
                : "Enable sound"}
        </button>
      </header>
      <div className="command-row">
        <label htmlFor="function-input">
          SR <b>›</b>
        </label>
        <form onSubmit={submit}>
          <input
            id="function-input"
            ref={field}
            autoComplete="off"
            placeholder="Enter function or ticker"
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              setNotice("");
            }}
          />
          <kbd>/</kbd>
          <button type="submit">
            GO <CornerDownLeft size={12} />
          </button>
        </form>
        <button
          className="help-key"
          aria-expanded={help}
          onClick={() => setHelp(!help)}
        >
          HELP
        </button>
      </div>
      {notice && (
        <div className="command-notice" role="status">
          {notice}
          <button
            onClick={() => setNotice("")}
            aria-label="Dismiss command message"
          >
            <X size={13} />
          </button>
        </div>
      )}
      {help && (
        <section className="function-menu">
          <header>
            Function directory
            <button
              aria-label="Close function directory"
              onClick={() => setHelp(false)}
            >
              <X size={15} />
            </button>
          </header>
          {functions.map(([c, n]) => (
            <button key={c} onClick={() => openFunction(c)}>
              <b>{c}</b>
              {n}
            </button>
          ))}
          <button
            onClick={() => {
              setMode("demo");
              setHelp(false);
            }}
          >
            <b>DEMO</b>Fictional replay
          </button>
        </section>
      )}
      <div className="rail">
        <nav aria-label="Terminal functions">
          {functions.map(([c, n]) => (
            <button
              key={c}
              aria-current={mode === "live" && page === c ? "page" : undefined}
              onClick={() => openFunction(c)}
              className={mode === "live" && page === c ? "active" : ""}
            >
              <b>{c}</b>
              {n}
            </button>
          ))}
        </nav>
        <div className="mode-toggle">
          <button
            className={mode === "live" ? "active" : ""}
            onClick={() => openFunction(page)}
          >
            Live
          </button>
          <button
            className={mode === "demo" ? "active" : ""}
            onClick={() => {
              setMode("demo");
              setNotice("");
            }}
          >
            Demo
          </button>
        </div>
      </div>
      {mode === "demo" ? (
        <div className="replay-terminal">
          <ReplayDesk playAlert={sound.play} />
        </div>
      ) : (
        <LiveDesk
          data={snapshot}
          playAlert={sound.play}
          {...{
            error,
            directory,
            page,
            setPage: openFunction,
            query,
            setQuery,
            now,
          }}
        />
      )}
    </div>
  );
}
createRoot(document.getElementById("root")).render(<Terminal />);
