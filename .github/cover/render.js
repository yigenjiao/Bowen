// 把 cover.html 截成 README 封面 / 社交分享图。
//
//   cd 仓库根目录
//   python3 -m http.server 8765 &
//   node .github/cover/render.js            # 需要 npm i playwright
//
// 网络受限时，可设 LOCAL_MODULES=/path/to/node_modules（内含 three 和 @fontsource/noto-sans-sc），
// 脚本会把 CDN / Google Fonts 请求换成本地文件。
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = path.join(__dirname, '..', '..', 'assets'); // 截图 cover.png，再转成 cover.webp / cover.jpg
const NM = process.env.LOCAL_MODULES;

(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 2400, height: 904 }, deviceScaleFactor: 1 });
  if (NM) {
    await page.route('https://cdn.jsdelivr.net/npm/three@0.169.0/**', r =>
      r.fulfill({ path: path.join(NM, 'three', r.request().url().split('three@0.169.0/')[1]), contentType: 'application/javascript' }));
    await page.route('https://fonts.googleapis.com/**', async r => {
      const dir = path.join(NM, '@fontsource', 'noto-sans-sc');
      const css = ['400.css', '900.css'].map(f => fs.readFileSync(path.join(dir, f), 'utf8')).join('\n')
        .replace(/url\(\.\/files\//g, 'url(https://local-fonts/');
      r.fulfill({ body: css, contentType: 'text/css' });
    });
    await page.route('https://local-fonts/**', r =>
      r.fulfill({ path: path.join(NM, '@fontsource', 'noto-sans-sc', 'files', r.request().url().split('local-fonts/')[1]), contentType: 'font/woff2' }));
  }
  await page.goto(`${BASE}/.github/cover/cover.html`);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
  await page.waitForTimeout(500);
  fs.mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: path.join(OUT, 'cover.png'), omitBackground: true });
  console.log('wrote', path.join(OUT, 'cover.png'));
  await browser.close();
})();
