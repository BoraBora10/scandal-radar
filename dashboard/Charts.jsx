import React, { useEffect, useId, useRef } from "react";

export function Trace({
  values,
  color = "var(--mint)",
  style = "line",
  large = false,
}) {
  const id = useId().replace(/:/g, "");
  const w = large ? 400 : 105,
    h = large ? 64 : 33;
  const min = Math.min(...values),
    max = Math.max(...values);
  const points = values.map((v, i) => [
    2 + (i * (w - 4)) / Math.max(1, values.length - 1),
    h - 5 - ((v - min) / (max - min || 1)) * (h - 13),
  ]);
  const path = points.map((p) => p.join(",")).join(" ");
  return (
    <svg
      className={large ? "trace large" : "trace"}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity=".20" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {style === "bar" ? (
        points.map(([x, y], i) => (
          <rect
            key={i}
            x={x}
            y={y}
            width={Math.max(2, w / values.length - 3)}
            height={h - y}
            rx="1"
            fill={color}
            opacity={0.38 + (0.62 * (i + 1)) / points.length}
          />
        ))
      ) : (
        <>
          <polygon
            points={`2,${h} ${path} ${w - 2},${h}`}
            fill={`url(#${id})`}
          />
          <polyline
            points={path}
            fill="none"
            stroke={color}
            strokeWidth={large ? 2 : 1.6}
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        </>
      )}
    </svg>
  );
}

// The scope encodes evidence type by sector and source order by distance.
export function Scope({ evidence, ticker, paused }) {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current,
      ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let width, height, animation;
    function draw(t) {
      ctx.clearRect(0, 0, width, height);
      const r = Math.min(width * 0.415, height * 0.4);
      const x = width * 0.5,
        y = height * 0.52;
      const pi = Math.PI;
      ctx.save();
      ctx.translate(x, y);
      function line(x1, y1, x2, y2, ink, weight = 0.8) {
        ctx.strokeStyle = ink;
        ctx.lineWidth = weight;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      function ring(radius, ink, weight = 0.8) {
        ctx.strokeStyle = ink;
        ctx.lineWidth = weight;
        ctx.beginPath();
        ctx.arc(0, 0, radius, 0, pi * 2);
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(31,66,46,.25)";
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, pi * 2);
      ctx.fill();
      for (let i = -6; i <= 6; i++) {
        const z = (r * i) / 6,
          edge = Math.sqrt(Math.max(0, r * r - z * z));
        line(z, -edge, z, edge, "#2c4436", 0.5);
        line(-edge, z, edge, z, "#2c4436", 0.5);
      }
      for (let i = 0; i < 8; i++) {
        let a = (i * pi) / 4;
        line(
          0,
          0,
          Math.cos(a) * r,
          Math.sin(a) * r,
          i % 2 ? "#304c3a" : "#4b6753",
          0.65,
        );
      }
      for (const n of [0.2, 0.4, 0.6, 0.8, 1])
        ring(n * r, n === 1 ? "#62846b" : "#45624d", n === 1 ? 1 : 0.75);
      for (let i = 0; i < 120; i++) {
        const a = (i * pi) / 60,
          len = i % 10 === 0 ? 6 : i % 5 === 0 ? 4 : 2;
        line(
          Math.cos(a) * (r + 2),
          Math.sin(a) * (r + 2),
          Math.cos(a) * (r + 2 + len),
          Math.sin(a) * (r + 2 + len),
          i % 5 === 0 ? "#748d79" : "#45634d",
        );
      }
      const angle =
        paused || reduced.matches ? -0.69 : ((t / 9000) % (2 * pi)) - 1.2;
      for (let j = 0; j < 60; j++) {
        const a = angle - (60 - j) * 0.017;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, r - 1, a, a + 0.019);
        ctx.closePath();
        ctx.fillStyle = `rgba(125,225,149,${0.004 + 0.19 * (j / 60) ** 2})`;
        ctx.fill();
      }
      line(0, 0, Math.cos(angle) * r, Math.sin(angle) * r, "#94d5a0", 1);
      ctx.textAlign = "center";
      ctx.font = "9px 'IBM Plex Mono', monospace";
      ctx.fillStyle = "#90a496";
      [
        [0, -r - 12, "000"],
        [r + 18, 3, "090"],
        [0, r + 17, "180"],
        [-r - 18, 3, "270"],
      ].forEach(([a, b, s]) => ctx.fillText(s, a, b));
      const xy = { report: -0.85, filing: 2.2, social: 3.72, routine: 1.45 };
      evidence.forEach((e, i) => {
        const base = xy[e.kind] ?? 0,
          a = base + 0.82 * (i % 3);
        const d = r * (0.69 - 0.12 * (i % 3)),
          bx = d * Math.cos(a),
          by = d * Math.sin(a);
        const ink = e.kind === "social" ? "#ead193" : "#b9f4c6";
        const g = ctx.createRadialGradient(bx, by, 0, bx, by, 13);
        g.addColorStop(0, "rgba(181,242,193,.32)");
        g.addColorStop(1, "rgba(181,242,193,0)");
        ctx.fillStyle = g;
        ctx.fillRect(bx - 13, by - 13, 26, 26);
        ctx.strokeStyle = ink;
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.arc(bx, by, 6, 0, 2 * pi);
        ctx.stroke();
        ctx.fillStyle = ink;
        ctx.beginPath();
        ctx.arc(bx, by, 2.7, 0, 2 * pi);
        ctx.fill();
        if (i === evidence.length - 1) {
          line(bx + 5, by - 4, bx + 15, by - 14, "#8dae96");
          line(bx + 15, by - 14, bx + 35, by - 14, "#8dae96");
          ctx.fillStyle = "#cae8cf";
          ctx.textAlign = "left";
          ctx.font = "9px 'IBM Plex Mono', monospace";
          ctx.fillText(ticker, bx + 16, by - 18);
        }
      });
      ctx.fillStyle = "#d5f9d9";
      ctx.fillRect(-1.5, -1.5, 3, 3);
      ctx.restore();
      if (!paused && !reduced.matches) animation = requestAnimationFrame(draw);
    }
    function resize() {
      cancelAnimationFrame(animation);
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw(performance.now());
    }
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    reduced.addEventListener("change", resize);
    return () => {
      cancelAnimationFrame(animation);
      observer.disconnect();
      reduced.removeEventListener("change", resize);
    };
  }, [evidence, ticker, paused]);
  return (
    <canvas
      ref={ref}
      className="scope"
      role="img"
      aria-label={`Source radar for ${ticker}, ${evidence.length} source records`}
    />
  );
}
