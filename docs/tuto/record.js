// Enregistre le tuto MonteurOS Studio (écran réel, curseur visible) + chronologie des étapes.
// Usage : node docs/tuto/record.js http://127.0.0.1:8770 <dossier_sortie>
const { chromium } = require(process.env.PLAYWRIGHT || "playwright");
const [, , BASE = "http://127.0.0.1:8765", OUT = "tuto-out"] = process.argv;
const W = 1600, H = 900;

const CURSOR = () => {
  const c = document.createElement("div");
  c.id = "__cur";
  c.style.cssText = "position:fixed;z-index:99999;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;" +
    "background:rgba(255,217,53,.35);border:2px solid #FFD935;pointer-events:none;transition:transform .12s;left:-50px;top:-50px";
  const add = () => document.body && !document.getElementById("__cur") && document.body.appendChild(c);
  document.addEventListener("DOMContentLoaded", add); setInterval(add, 300);
  addEventListener("mousemove", e => { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }, true);
  addEventListener("mousedown", () => c.style.transform = "scale(.6)", true);
  addEventListener("mouseup", () => c.style.transform = "scale(1)", true);
};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: OUT, size: { width: W, height: H } } });
  await ctx.addInitScript(CURSOR);
  const page = await ctx.newPage();
  const t0 = Date.now(), marks = [];
  const mark = (id) => marks.push({ id, t: (Date.now() - t0) / 1000 });
  const wait = ms => page.waitForTimeout(ms);
  let mx = W / 2, my = H / 2;
  const moveTo = async (sel, opt = {}) => {
    const el = page.locator(sel).first();
    await el.scrollIntoViewIfNeeded().catch(() => {});
    const b = await el.boundingBox();
    if (!b) return el;
    const x = b.x + b.width * (opt.fx ?? .5), y = b.y + b.height * (opt.fy ?? .5);
    await page.mouse.move(x, y, { steps: 28 }); mx = x; my = y;
    await wait(opt.pause ?? 350);
    return el;
  };
  const click = async (sel, opt) => { await moveTo(sel, opt); await page.mouse.down(); await wait(90); await page.mouse.up(); await wait(opt?.after ?? 900); };
  const type = async (sel, text) => { await click(sel, { after: 200 }); await page.keyboard.type(text, { delay: 55 }); await wait(400); };
  const scroll = async (dy, steps = 12) => { for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, dy / steps); await wait(45); } await wait(500); };

  // 1 · Projets
  await page.goto(BASE + "/#/projets"); await wait(1800); mark("projets");
  await moveTo(".stat:nth-child(1)", { pause: 900 }); await moveTo(".stat:nth-child(2)", { pause: 700 });
  await moveTo(".stat:nth-child(3)", { pause: 700 }); await moveTo(".stat:nth-child(4)", { pause: 900 });
  await type("#q", "inter"); await wait(900);
  await page.fill("#q", ""); await page.dispatchEvent("#q", "input"); await wait(600);
  await moveTo(".filters select[data-f=status]", { pause: 700 });
  await moveTo(".card:has-text('Interview')", { pause: 1200 });

  // 2 · Le projet
  await click(".card:has-text('Interview')", { after: 1800 }); mark("projet");
  await moveTo(".deliv div[data-r]", { pause: 900 });
  await page.evaluate(() => { const v = document.querySelector("#pv"); v.muted = true; v.play(); }); await wait(2500);
  await moveTo(".checks", { pause: 1500 });
  await scroll(520); mark("actions");
  await moveTo(".actions [data-a=prep]", { pause: 900 });
  await click(".actions [data-a=draft]", { after: 600 });
  await moveTo("#joblog", { pause: 6500 });

  // 3 · Retours frame par frame
  await scroll(-900); await click("a.btn.y:has-text('Apporter')", { after: 1400 }); mark("retours");
  await page.selectOption("#rd", { label: "interview-coach-v02-master.mp4" }).catch(() => {}); await wait(900);
  await click("#play", { after: 2200 }); await click("#play", { after: 600 });
  for (let i = 0; i < 4; i++) await click("[data-f='1']", { after: 280 });
  await click("[data-s='1']", { after: 500 });
  await type("#fbtxt", "Coupe ce silence juste avant la carte");
  await click("#fbadd", { after: 1200 });
  await click("#fbl [data-t]", { after: 1000 });
  await moveTo("#copy", { pause: 900 });
  await click("#send", { after: 1800 });

  // 4 · Studio
  await click("nav a[data-v=studio]", { after: 1200 });
  await page.selectOption("#sp", "interview-coach.mp4"); await wait(2200); mark("studio");
  await moveTo("#ts", { pause: 600 }); await click("#ts span[data-i='6']", { after: 800 });
  await moveTo("#tl .trk:nth-of-type(2)", { pause: 900 }); await moveTo("#tl .trk:nth-of-type(4)", { pause: 900 });
  await click("#tl .blk.an", { after: 1200 });
  await moveTo("#cardsel", { pause: 500 }); await page.selectOption("#cardsel", "stat.courbe"); await wait(800);
  await page.fill("[data-cv=value]", ""); await type("[data-cv=value]", "5");
  await page.fill("[data-cv=suffix]", ""); await type("[data-cv=unit]", " histoires");
  await click("#cardprev", { after: 4800 }); mark("apercu");
  await click("#mclose", { after: 900 });
  await moveTo("#cardput", { pause: 1200 });

  // 5 · Bibliothèques
  await click("nav a[data-v=bibliotheques]", { after: 2000 }); mark("biblio");
  await moveTo("[data-fmt]", { pause: 1200 });
  await scroll(420); await moveTo("[data-theme], .pill.y", { pause: 1200 });
  await scroll(520); await moveTo("[data-style=nocturne]", { pause: 900 });
  await click("[data-style=nocturne]", { after: 3800 }); mark("style");
  await scroll(500); await wait(1500);
  await click("[data-open='ecran.push3d']", { after: 4500 }); await click("#mclose", { after: 800 });

  // 6 · Activité
  await click("nav a[data-v=activite]", { after: 2500 }); mark("activite");
  await moveTo(".tbl tr:nth-child(2)", { pause: 2500 });
  await click("nav a[data-v=projets]", { after: 2200 }); mark("fin");

  require("fs").writeFileSync(`${OUT}/marks.json`, JSON.stringify(marks, null, 1));
  await ctx.close(); await browser.close();
  console.log(JSON.stringify(marks));
})();
