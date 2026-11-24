import { build } from "esbuild";
import { execFileSync } from "node:child_process";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const assets = join(root, "../farmbot/assets");
const modules = join(root, "node_modules");

const bundle = await build({
  absWorkingDir: root,
  entryPoints: ["src/main.jsx"],
  bundle: true,
  jsx: "automatic",
  minify: true,
  format: "esm",
  target: "es2022",
  define: { "process.env.NODE_ENV": '"production"' },
  legalComments: "eof",
  metafile: true,
  write: false,
});

const css = execFileSync(process.execPath, [
  join(modules, "@tailwindcss/cli/dist/index.mjs"),
  "-i", "src/dashboard.css", "--minify",
], { cwd: root, stdio: ["ignore", "pipe", "inherit"] });

const dependencies = new Set(["node_modules/tailwindcss"]);
for (const path of Object.keys(bundle.metafile.inputs)) {
  const marker = "node_modules/";
  const offset = path.lastIndexOf(marker);
  if (offset === -1) continue;
  const parts = path.slice(offset + marker.length).split("/");
  const name = parts.slice(0, parts[0].startsWith("@") ? 2 : 1).join("/");
  dependencies.add(path.slice(0, offset + marker.length) + name);
}

const licenses = new Map();
const upstreamLicenses = {
  "@ant-design/icons-svg": "ant-design-icons-svg.txt",
  "is-mobile": "is-mobile.txt",
};
for (const dependency of [...dependencies].sort()) {
  const folder = join(root, dependency);
  const manifest = JSON.parse(await readFile(join(folder, "package.json"), "utf8"));
  const files = (await readdir(folder)).filter((name) => /^(licen[cs]e|copying|notice)(\.|$)/i.test(name))
    .sort().map((name) => join(folder, name));
  if (!files.length && upstreamLicenses[manifest.name]) files.push(join(root, "licenses", upstreamLicenses[manifest.name]));
  if (!files.length) throw new Error("Missing license for " + manifest.name);
  const texts = await Promise.all(files.map((file) => readFile(file, "utf8")));
  const license = texts.map((text) => text.trim()).join("\n\n");
  const names = licenses.get(license) || [];
  names.push(manifest.name + " " + manifest.version);
  licenses.set(license, names);
}

const notices = [...licenses].map(([license, names]) => names.join("\n") + "\n\n" + license);
const noticeText = notices.join("\n\n---\n\n").replaceAll("\r\n", "\n").replace(/[ \t]+$/gm, "");
await writeFile(join(assets, "dashboard.js"), bundle.outputFiles[0].text.replace(/[ \t]+$/gm, ""));
await writeFile(join(assets, "dashboard.css"), css);
await writeFile(join(assets, "dashboard.LICENSE.txt"), noticeText + "\n");
