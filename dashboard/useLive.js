import { useEffect, useState } from "react";
export const localTransport =
  document.querySelector('meta[name="radar-transport"]')?.content ===
  "websocket";
export function useLive(enabled) {
  const [snapshot, setSnapshot] = useState(null),
    [error, setError] = useState(""),
    [directory, setDirectory] = useState(null);
  useEffect(() => {
    if (!enabled) return;
    let closed = false,
      timer,
      socket;
    const controller = new AbortController();
    async function read() {
      try {
        const res = await fetch("/api/live", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!res.ok)
          throw Error(
            res.status === 503
              ? "Waiting for the collector"
              : "Snapshot unavailable",
          );
        const data = await res.json();
        if (!Array.isArray(data.sources)) throw Error("Unexpected response");
        if (!closed) {
          setSnapshot(data);
          setError("");
        }
      } catch (e) {
        if (!closed) setError(e.message || "Connection interrupted");
      }
      if (!closed && !localTransport) timer = setTimeout(read, 12000);
    }
    function connect() {
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/live`,
      );
      socket.onmessage = (e) => {
        if (!closed) {
          setSnapshot(JSON.parse(e.data));
          setError("");
        }
      };
      socket.onclose = () => {
        if (!closed) {
          setError("Collector disconnected");
          timer = setTimeout(connect, 4000);
        }
      };
    }
    read();
    if (localTransport) connect();
    return () => {
      closed = true;
      controller.abort();
      clearTimeout(timer);
      socket?.close();
    };
  }, [enabled]);
  const version = snapshot?.directory?.as_of;
  useEffect(() => {
    if (!enabled || !version) return;
    let done = false,
      id;
    const ctl = new AbortController();
    async function getDirectory() {
      try {
        const r = await fetch("/api/directory", {
          cache: "no-store",
          signal: ctl.signal,
        });
        if (!r.ok) throw Error();
        const data = await r.json();
        if (!done) setDirectory(data);
      } catch {
        if (!done) id = setTimeout(getDirectory, 12000);
      }
    }
    getDirectory();
    return () => {
      done = true;
      ctl.abort();
      clearTimeout(id);
    };
  }, [version, enabled]);
  return { snapshot, error, directory };
}
