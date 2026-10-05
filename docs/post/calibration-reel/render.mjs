// node render.mjs --fps 60 --dur 15 --sub 4 --w 1080 --h 1920 --out out/silent.mp4
// --from S --dur D renders only seconds S..S+D (for fixing one section). --dur defaults to window.DUR - from.
// --sub N renders N subframes per frame and averages them (motion blur). Use --sub 1 for drafts.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const FPS = Number(arg('fps', 60)), SUB = Number(arg('sub', 1));
const W = Number(arg('w', 1080)), H = Number(arg('h', 1920));
const OUT = arg('out', 'out/silent.mp4'), HTML = resolve(arg('html', 'index.html'));
mkdirSync(dirname(OUT), { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
await page.goto(`file://${HTML}?w=${W}&h=${H}`);
await page.evaluate(() => window.READY);                // fonts and images loaded before the first frame
const FROM = Number(arg('from', 0));
const DUR = Number(arg('dur', (await page.evaluate(() => window.DUR)) - FROM));

// tmix averages SUB consecutive subframes; select keeps the last of each group
const vf = SUB > 1 ? `tmix=frames=${SUB},select='eq(mod(n\\,${SUB})\\,${SUB - 1})',setpts=N/${FPS}/TB` : 'null';
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS * SUB), '-i', '-',
  '-vf', vf, '-r', String(FPS), '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', OUT],
  { stdio: ['pipe', 'inherit', 'inherit'] });

const total = Math.round(DUR * FPS * SUB);
for (let i = 0; i < total; i++) {
  await page.evaluate((t) => window.seek(t), FROM + i / (FPS * SUB));
  const png = await page.locator('#c').screenshot({ type: 'png' });
  if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once('drain', r));
  if (i % (FPS * SUB) === 0) console.log(`rendered ${i / (FPS * SUB)}s / ${DUR}s`);
}
ff.stdin.end();
const code = await new Promise((r) => ff.on('close', r));
await browser.close();
if (code !== 0) { console.error(`ffmpeg exited ${code}`); process.exit(1); }
console.log(`wrote ${OUT}`);
