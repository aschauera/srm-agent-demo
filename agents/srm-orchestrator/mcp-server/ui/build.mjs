import { build } from "esbuild";
import { mkdir, readFile, writeFile } from "node:fs/promises";

const result = await build({
  entryPoints: ["app.ts"],
  bundle: true,
  format: "iife",
  target: "es2022",
  minify: true,
  write: false,
});
const template = await readFile("index.html", "utf8");
const javascript = result.outputFiles[0].text.replace(/<\/script/gi, "<\\/script");
await mkdir("../dist", { recursive: true });
await writeFile("../dist/dashboard.html", template.replace("/* MCP_APP_BUNDLE */", () => javascript));
