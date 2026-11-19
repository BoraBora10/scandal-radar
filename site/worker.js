const paths = new Map([
  ["/api/live", "live"],
  ["/api/directory", "directory"],
]);
const json = (body, status = 200) =>
  Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
export default {
  async fetch(request, env) {
    const pathname = new URL(request.url).pathname;
    const key = paths.get(pathname);
    if (key) {
      if (request.method === "GET") {
        const row = await env.DB.prepare(
          "SELECT payload FROM dashboard_state WHERE kind=?",
        )
          .bind(key)
          .first();
        return row
          ? new Response(row.payload, {
              headers: {
                "Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-store",
              },
            })
          : json({ error: "Waiting for the first collector update." }, 503);
      }
      if (request.method !== "PUT")
        return json({ error: "Unsupported method" }, 405);
      if (
        !env.RADAR_WRITE_KEY ||
        request.headers.get("X-Radar-Writer") !== env.RADAR_WRITE_KEY
      )
        return json({ error: "Writer authentication required" }, 403);
      const raw = await request.text();
      if (new TextEncoder().encode(raw).length > 1800000)
        return json({ error: "Payload too large" }, 413);
      let data;
      try {
        data = JSON.parse(raw);
      } catch {
        return json({ error: "Invalid JSON" }, 400);
      }
      const revision =
        key === "live" ? data?.as_of : Date.parse(data?.fetched_at) / 1000;
      if (
        !Number.isFinite(revision) ||
        !(key === "live"
          ? Array.isArray(data.records) && Array.isArray(data.sources)
          : Array.isArray(data.companies))
      )
        return json({ error: "Invalid snapshot" }, 422);
      await env.DB.prepare(
        "INSERT INTO dashboard_state(kind,revision,payload) VALUES (?,?,?) ON CONFLICT(kind) DO UPDATE SET revision=excluded.revision,payload=excluded.payload WHERE excluded.revision>=dashboard_state.revision",
      )
        .bind(key, revision, raw)
        .run();
      return json({ saved: true, revision });
    }
    if (request.method !== "GET" && request.method !== "HEAD")
      return new Response(null, { status: 405 });
    const asset = ASSETS[pathname === "/" ? "/index.html" : pathname];
    if (!asset) return new Response("Not found", { status: 404 });
    const binary = atob(asset[1]);
    const headers = {
      "Content-Type": asset[0],
      "Cache-Control": pathname.startsWith("/assets/")
        ? "public,max-age=31536000,immutable"
        : "no-cache",
      "X-Content-Type-Options": "nosniff",
    };
    return new Response(
      request.method === "HEAD"
        ? null
        : Uint8Array.from(binary, (c) => c.charCodeAt(0)),
      { headers },
    );
  },
};
