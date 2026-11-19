import { useCallback, useEffect, useRef, useState } from "react";
import { playChime } from "./matchAlerts";

const preference = "radar.alertSound";
const AudioEngine = window.AudioContext || window.webkitAudioContext;

export function useAlertSound() {
  const context = useRef(null);
  const wanted = useRef(true);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  const play = useCallback(() => {
    if (wanted.current) playChime(context.current);
  }, []);

  const enable = useCallback(
    async (preview = false) => {
      if (!AudioEngine || !wanted.current) return;
      try {
        if (!context.current || context.current.state === "closed") {
          const audio = new AudioEngine();
          context.current = audio;
          audio.onstatechange = () =>
            setReady(wanted.current && audio.state === "running");
        }
        const audio = context.current;
        await audio.resume();
        if (context.current !== audio || !wanted.current) return;
        setReady(audio.state === "running");
        setFailed(false);
        if (preview) play();
      } catch {
        setReady(false);
        setFailed(true);
      }
    },
    [play],
  );

  useEffect(() => {
    try {
      wanted.current = localStorage.getItem(preference) !== "muted";
    } catch {}
    function unlock(event) {
      if (!event.isTrusted || event.target?.closest?.("[data-alert-sound]"))
        return;
      if (wanted.current && context.current?.state !== "running") void enable();
    }
    document.addEventListener("click", unlock);
    document.addEventListener("keydown", unlock);
    return () => {
      document.removeEventListener("click", unlock);
      document.removeEventListener("keydown", unlock);
      const audio = context.current;
      context.current = null;
      if (audio) {
        audio.onstatechange = null;
        void audio.close().catch(() => {});
      }
    };
  }, [enable]);

  function toggle() {
    wanted.current = !ready;
    try {
      localStorage.setItem(preference, ready ? "muted" : "on");
    } catch {}
    if (ready) {
      setReady(false);
      void context.current?.suspend().catch(() => {});
    } else {
      void enable(true);
    }
  }
  return { ready, failed, supported: Boolean(AudioEngine), play, toggle };
}
