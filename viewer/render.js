const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = __dirname, THREE = '/tmp/threepkg/node_modules/three';
const OUT = process.argv[2]; const ONLY = process.argv[3] ? process.argv[3].split(',') : null;
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  fs.readFile(p, (err, data) => { if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': p.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/json' }); res.end(data); });
});
const shots = JSON.parse(fs.readFileSync(path.join(ROOT, 'shots.json'), 'utf8'));
(async () => {
  await new Promise(r => server.listen(8771, r));
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  for (const s of shots) {
    if (ONLY && !ONLY.includes(s.name)) continue;
    const ctx = await browser.newContext({ viewport: { width: s.w || 1360, height: s.h || 860 }, colorScheme: 'light', deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    await page.route('https://cdn.jsdelivr.net/npm/three@0.160.0/**', route => {
      route.fulfill({ path: path.join(THREE, route.request().url().replace('https://cdn.jsdelivr.net/npm/three@0.160.0/', '')), contentType: 'application/javascript' }); });
    await page.route('https://fonts.googleapis.com/**', r => r.fulfill({ body: '', contentType: 'text/css' }));
    await page.route('https://fonts.gstatic.com/**', r => r.abort());
    await page.goto('http://localhost:8771/index.html');
    await page.waitForFunction(() => window.__bp && document.getElementById('loading').hidden === true, null, { timeout: 120000 });
    await page.addStyleTag({ content: '.hud{display:none!important}' });
    if (s.case && s.case !== 'solid') await page.click(`[data-case="${s.case}"]`);
    if (!s.labels) await page.click('#labelsOn');
    await page.evaluate((s) => {
      const bp = window.__bp;
      if (s.explode) bp.applyExplode(s.explode);
      if (s.hideParts || s.onlyGroups) {
        for (const [name, node] of bp.nodes) {
          const p = bp.byName.get(name);
          if (s.onlyGroups && !s.onlyGroups.includes(p.group)) node.visible = false;
          if (s.hideParts && s.hideParts.some(h => name.startsWith(h))) node.visible = false;
          if (s.showParts && s.showParts.some(h => name.startsWith(h))) node.visible = true;
        }
        bp.updateTags();
      }
      for (const el of document.querySelectorAll('.tag')) if ((s.hide || []).includes(el.textContent.trim())) el.style.visibility = 'hidden';
      const key = bp.scene.children.find(o => o.isDirectionalLight);
      const fill = key.clone(); fill.intensity = (s.dir[2] < 0 || s.dir[1] < 0) ? 1.3 : 0.35;
      fill.position.set(s.dir[0] * 400 + 120, s.dir[1] * 400 + 160, s.dir[2] * 400); bp.scene.add(fill);
      bp.controls.enableDamping = false;
      const t = new bp.camera.position.constructor(...s.tgt);
      const d = new bp.camera.position.constructor(...s.dir).normalize().multiplyScalar(s.dist);
      bp.camera.position.copy(t.clone().add(d)); bp.controls.target.copy(t); bp.controls.update();
    }, s);
    await page.waitForTimeout(1500);
    await page.locator('#stage').screenshot({ path: path.join(OUT, s.name + '.png'), timeout: 180000 });
    console.log(s.name);
    await ctx.close();
  }
  await browser.close(); server.close();
})().catch(e => { console.error(e); process.exit(1); });
