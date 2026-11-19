import { useCallback, useEffect, useRef, useState } from "react";
import tape from "./replay.json";

export const sourceList = tape.sources;
const localServer =
  document.querySelector('meta[name="radar-transport"]')?.content ===
  "websocket";
function snapshot(index, speed, paused = false) {
  return {
    index,
    speed,
    paused,
    frame: tape.frames[index],
    ended: index === tape.frames.length - 1,
  };
}

export function useReplay() {
  const [state, setState] = useState(() => snapshot(tape.initial, 1));
  const [connected, setConnected] = useState(!localServer);
  const socket = useRef(null);

  useEffect(() => {
    if (!localServer) return;
    let disposed = false;
    let retry;
    function connect() {
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`,
      );
      socket.current = ws;
      ws.onmessage = ({ data }) => {
        setState(JSON.parse(data));
        setConnected(true);
      };
      ws.onclose = () => {
        if (disposed) return;
        setConnected(false);
        retry = setTimeout(connect, 2000);
      };
    }
    connect();
    return () => {
      disposed = true;
      clearTimeout(retry);
      socket.current?.close();
    };
  }, []);

  useEffect(() => {
    if (localServer || state.paused || state.ended) return;
    const id = setTimeout(
      () => setState((s) => snapshot(s.index + 1, s.speed)),
      10000 / state.speed,
    );
    return () => clearTimeout(id);
  }, [state.index, state.paused, state.speed, state.ended]);

  const command = useCallback((action, value) => {
    if (localServer) {
      if (socket.current?.readyState === WebSocket.OPEN)
        socket.current.send(JSON.stringify({ action, value }));
      return;
    }
    setState((s) => {
      if (action === "replay") return snapshot(0, s.speed);
      if (action === "pause") return { ...s, paused: !s.paused };
      if (action === "speed") return { ...s, speed: value };
      return s;
    });
  }, []);
  return { ...state, command, connected };
}
