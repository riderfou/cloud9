// Capture d'écran de la webapp (test local) : node tools/screenshot.mjs <url> <sortie.png> [largeur] [hauteur]
// Les URL du CDN three.js sont servies depuis une copie locale (le CDN n'est pas joignable depuis le conteneur).
import { createRequire } from "module";
const { chromium } = createRequire(import.meta.url)("playwright");
import fs from "fs";
const [url, out, w = "1500", h = "900"] = process.argv.slice(2);
const LOCAL = process.env.THREE_LOCAL || "/tmp/t3/node_modules/three";
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
page.on("console", (m) => console.log("[console]", m.type(), m.text()));
page.on("pageerror", (e) => console.log("[pageerror]", e.message));
await page.route("https://cdn.jsdelivr.net/npm/three@0.170.0/**", (route) => {
  const p = new URL(route.request().url()).pathname.replace("/npm/three@0.170.0", "");
  route.fulfill({ body: fs.readFileSync(LOCAL + p), contentType: "application/javascript" });
});
await page.goto(url);
await page.waitForFunction(() => !document.getElementById("loading"), null, { timeout: 60000 }).catch(() => console.log("timeout chargement"));
await page.waitForTimeout(2500);
if (process.env.CLICK) for (const s of process.env.CLICK.split(",")) { await page.evaluate((sel) => document.querySelector(sel).click(), s); await page.waitForTimeout(800); }
await page.screenshot({ path: out });
await browser.close();
