import { readFile, writeFile, readdir, mkdir } from "node:fs/promises";
import { extname, join, relative } from "node:path";
const root = "dist/client";
const types = {
  ".js": "text/javascript",
  ".css": "text/css",
  ".html": "text/html; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
};
const assets = {};
async function collect(path) {
  for (const entry of await readdir(path, { withFileTypes: true })) {
    const file = join(path, entry.name);
    if (entry.isDirectory()) await collect(file);
    else
      assets["/" + relative(root, file)] = [
        types[extname(file)] ?? "application/octet-stream",
        (await readFile(file)).toString("base64"),
      ];
  }
}
await collect(root);
await mkdir("dist/server", { recursive: true });
await writeFile(
  "dist/server/index.js",
  "const ASSETS=" +
    JSON.stringify(assets) +
    ";\n" +
    (await readFile("site/worker.js", "utf8")),
);
