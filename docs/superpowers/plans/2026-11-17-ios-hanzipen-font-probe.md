# iOS HanziPen Font Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore Dayfold's accepted HanziPen typography unchanged and determine, on a physical iPhone, whether Safari can resolve the same local font through its family or PostScript name.

**Architecture:** Keep the product page on the original device-local font stack. Add a separate static probe made of HTML, CSS, and JavaScript files so the existing Vercel CSP remains intact; the probe uses dedicated local-only `@font-face` declarations plus Font Loading API and canvas signatures to distinguish a real HanziPen load from fallback rendering. Treat the physical-iPhone result as a hard gate: add a local alias only when the regular family or W3 face passes, otherwise stop without substituting another font.

**Tech Stack:** Static HTML/CSS/JavaScript, CSS Font Loading API, Canvas 2D, Pytest, Vercel Preview, physical iPhone Safari

---

## File Structure

### Probe Phase

- Modify `apps/api/tests/test_health.py`
  - Replace the rejected self-hosted-font regression test.
  - Assert the original typography baseline.
  - Assert the isolated probe structure and privacy boundaries.
- Modify `apps/web/index.html`
  - Remove the LXGW webfont stylesheet link.
- Modify `apps/web/styles.css`
  - Restore the original HanziPen-led stack without changing any other rule.
- Delete `apps/web/assets/fonts/`
  - Remove the rejected LXGW WenKai Lite webfont and license bundle.
- Create `apps/web/font-probe.html`
  - Provide a standalone, unlinked diagnostic surface.
- Create `apps/web/font-probe.css`
  - Declare the three local-only probe families and probe presentation.
- Create `apps/web/font-probe.js`
  - Evaluate local font availability without sending or persisting results.

### Conditional Alias Phase

- Modify `apps/api/tests/test_health.py`
  - Assert the accepted local alias mapping.
- Modify `apps/web/styles.css`
  - Add `Dayfold HanziPen` local aliases only if `HanziPen SC` or
    `HanziPenSC-W3` passes on the physical iPhone.

### Cleanup Phase

- Delete `apps/web/font-probe.html`
- Delete `apps/web/font-probe.css`
- Delete `apps/web/font-probe.js`
- Modify `apps/api/tests/test_health.py`
  - Remove temporary probe assertions while retaining the production alias
    regression.

No API route, authentication, database, Memory, Chat, Growth, retrieval,
deployment configuration, product copy, spacing, or color file is changed.

---

### Task 1: Restore The Accepted Typography Baseline

**Files:**
- Modify: `apps/api/tests/test_health.py:1-146`
- Modify: `apps/web/index.html:11-17`
- Modify: `apps/web/styles.css:1-15`
- Delete: `apps/web/assets/fonts/`

- [ ] **Step 1: Replace the rejected webfont test with a failing baseline test**

Remove the now-unused `re` import from `apps/api/tests/test_health.py`.

Replace `test_web_self_hosts_chinese_handwriting_font` with:

```python
def test_web_preserves_original_hanzipen_typography_without_webfont_override():
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    stylesheet = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")
    font_root = WEB_ROOT / "assets" / "fonts"

    assert './assets/fonts/dayfold-hand.css' not in html
    assert '"Dayfold Hand"' not in stylesheet
    assert (
        '"HanziPen SC", "HanziPen TC", "Bradley Hand", "Klee", '
        '"PingFang SC",'
    ) in stylesheet
    assert not font_root.exists()
```

- [ ] **Step 2: Run the baseline test and verify it fails**

Run:

```bash
PYTHONPATH=. uv run --with-requirements apps/api/requirements.txt \
  pytest -p no:cacheprovider \
  apps/api/tests/test_health.py::test_web_preserves_original_hanzipen_typography_without_webfont_override \
  -v
```

Expected: FAIL because `index.html` still loads `dayfold-hand.css`, `styles.css`
still starts with `"Dayfold Hand"`, and the bundled font directory still exists.

- [ ] **Step 3: Remove the rejected stylesheet link**

Change `apps/web/index.html` from:

```html
<link rel="stylesheet" href="./assets/fonts/dayfold-hand.css">
<link rel="stylesheet" href="./styles.css">
```

to:

```html
<link rel="stylesheet" href="./styles.css">
```

- [ ] **Step 4: Restore the original CSS stack exactly**

Change the `:root` font declaration in `apps/web/styles.css` to:

```css
font-family: "HanziPen SC", "HanziPen TC", "Bradley Hand", "Klee", "PingFang SC",
  sans-serif;
```

Do not change font sizes, weights, letter spacing, line heights, colors, or any
other selector.

- [ ] **Step 5: Delete the rejected self-hosted assets**

Run:

```bash
git rm -r apps/web/assets/fonts
```

Expected: 100 tracked font-related files are removed, including the generated
CSS, OFL notice, and 97 WOFF2 subsets.

- [ ] **Step 6: Run the baseline test and verify it passes**

Run:

```bash
PYTHONPATH=. uv run --with-requirements apps/api/requirements.txt \
  pytest -p no:cacheprovider \
  apps/api/tests/test_health.py::test_web_preserves_original_hanzipen_typography_without_webfont_override \
  -v
```

Expected: PASS.

- [ ] **Step 7: Verify the baseline diff is surgical**

Run:

```bash
git diff --check
git diff -- apps/web/index.html apps/web/styles.css apps/api/tests/test_health.py
```

Expected: only the webfont link, first font-family entry, rejected regression
test, and `re` import change; no typography dimensions or unrelated styles move.

- [ ] **Step 8: Commit the baseline restoration**

```bash
git add apps/api/tests/test_health.py apps/web/index.html apps/web/styles.css
git commit -m "fix(web): restore original handwriting baseline"
```

The deleted `apps/web/assets/fonts/` paths are already staged by `git rm`.

---

### Task 2: Add The Isolated iOS Font Probe

**Files:**
- Modify: `apps/api/tests/test_health.py:123-149`
- Create: `apps/web/font-probe.html`
- Create: `apps/web/font-probe.css`
- Create: `apps/web/font-probe.js`

- [ ] **Step 1: Write the failing probe regression test**

Add this test immediately after the typography-baseline test:

```python
def test_web_exposes_private_local_hanzipen_probe():
    product_html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    probe_html = (WEB_ROOT / "font-probe.html").read_text(encoding="utf-8")
    probe_css = (WEB_ROOT / "font-probe.css").read_text(encoding="utf-8")
    probe_js = (WEB_ROOT / "font-probe.js").read_text(encoding="utf-8")

    assert "font-probe" not in product_html
    assert '<link rel="stylesheet" href="./font-probe.css">' in probe_html
    assert '<script src="./font-probe.js" defer></script>' in probe_html
    assert "<style" not in probe_html
    assert "<script>" not in probe_html

    for local_name in ("HanziPen SC", "HanziPenSC-W3", "HanziPenSC-W5"):
        assert f'local("{local_name}")' in probe_css

    assert "document.fonts" in probe_js
    assert "getImageData" in probe_js
    assert "navigator.userAgent" in probe_js
    assert "fetch(" not in probe_js
    assert "sendBeacon" not in probe_js
    assert "localStorage" not in probe_js
    assert "sessionStorage" not in probe_js
```

- [ ] **Step 2: Run the probe test and verify it fails**

Run:

```bash
PYTHONPATH=. uv run --with-requirements apps/api/requirements.txt \
  pytest -p no:cacheprovider \
  apps/api/tests/test_health.py::test_web_exposes_private_local_hanzipen_probe \
  -v
```

Expected: FAIL with `FileNotFoundError` for `apps/web/font-probe.html`.

- [ ] **Step 3: Create the CSP-compatible probe HTML**

Create `apps/web/font-probe.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex,nofollow">
    <title>Dayfold iOS Font Probe</title>
    <link rel="stylesheet" href="./font-probe.css">
    <script src="./font-probe.js" defer></script>
  </head>
  <body>
    <main>
      <header>
        <p class="eyebrow">Dayfold diagnostic</p>
        <h1>iOS HanziPen Probe</h1>
        <p>
          此页面只在当前浏览器检测本地字体，不上传或保存结果。
        </p>
        <p id="environment" class="environment"></p>
      </header>

      <section class="probe-list" aria-labelledby="results-title">
        <h2 id="results-title">检测结果</h2>

        <article class="probe" data-probe="family">
          <div class="probe-head">
            <h3>HanziPen SC</h3>
            <strong data-status>检测中</strong>
          </div>
          <p class="sample probe-family">写下今天。Dayfold remembers.</p>
          <p data-detail class="detail"></p>
        </article>

        <article class="probe" data-probe="w3">
          <div class="probe-head">
            <h3>HanziPenSC-W3</h3>
            <strong data-status>检测中</strong>
          </div>
          <p class="sample probe-w3">写下今天。Dayfold remembers.</p>
          <p data-detail class="detail"></p>
        </article>

        <article class="probe" data-probe="w5">
          <div class="probe-head">
            <h3>HanziPenSC-W5</h3>
            <strong data-status>检测中</strong>
          </div>
          <p class="sample probe-w5">写下今天。Dayfold remembers.</p>
          <p data-detail class="detail"></p>
        </article>
      </section>

      <section aria-labelledby="summary-title">
        <h2 id="summary-title">可复制结果</h2>
        <pre id="result-summary" aria-live="polite">正在检测……</pre>
      </section>
    </main>
  </body>
</html>
```

- [ ] **Step 4: Create local-only font declarations and quiet probe styling**

Create `apps/web/font-probe.css`:

```css
@font-face {
  font-family: "Probe HanziPen Family";
  src: local("HanziPen SC");
  font-style: normal;
  font-weight: 400;
}

@font-face {
  font-family: "Probe HanziPen W3";
  src: local("HanziPenSC-W3");
  font-style: normal;
  font-weight: 400;
}

@font-face {
  font-family: "Probe HanziPen W5";
  src: local("HanziPenSC-W5");
  font-style: normal;
  font-weight: 400;
}

:root {
  color-scheme: light;
  font-family: system-ui, -apple-system, "PingFang SC", sans-serif;
  background: #c7e8f8;
  color: #17191b;
}

* {
  box-sizing: border-box;
}

body {
  min-width: 320px;
  min-height: 100vh;
  margin: 0;
  background:
    repeating-linear-gradient(
      0deg,
      transparent 0,
      transparent 31px,
      rgb(65 111 135 / 8%) 32px
    ),
    #c7e8f8;
}

main {
  width: min(100% - 28px, 720px);
  margin: 0 auto;
  padding: 32px 0;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

.eyebrow,
.environment,
.detail {
  color: #526774;
  font-size: 0.78rem;
}

.probe-list {
  margin-top: 36px;
}

.probe {
  padding: 22px 0;
  border-top: 1px solid #9fc4d7;
}

.probe-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.probe [data-status="pass"] {
  color: #316e5b;
}

.probe [data-status="fail"] {
  color: #8a3f39;
}

.sample {
  min-height: 58px;
  margin-bottom: 8px;
  font-size: 1.75rem;
  line-height: 1.45;
}

.probe-family {
  font-family: "Probe HanziPen Family", monospace;
}

.probe-w3 {
  font-family: "Probe HanziPen W3", monospace;
}

.probe-w5 {
  font-family: "Probe HanziPen W5", monospace;
}

pre {
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  border-top: 1px solid #416f87;
  padding-top: 14px;
  font: 0.78rem/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;
}
```

- [ ] **Step 5: Implement fallback-resistant local font detection**

Create `apps/web/font-probe.js`:

```javascript
const SAMPLE_TEXT = "写下今天。Dayfold remembers.";
const PROBES = [
  { id: "family", localName: "HanziPen SC", family: "Probe HanziPen Family" },
  { id: "w3", localName: "HanziPenSC-W3", family: "Probe HanziPen W3" },
  { id: "w5", localName: "HanziPenSC-W5", family: "Probe HanziPen W5" },
];

function normalizeFamily(value) {
  return value.replaceAll('"', "").replaceAll("'", "");
}

function renderSignature(family) {
  const canvas = document.createElement("canvas");
  canvas.width = 900;
  canvas.height = 120;
  const context = canvas.getContext("2d", { willReadFrequently: true });

  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#000";
  context.font = `48px "${family}", monospace`;
  context.textBaseline = "top";
  context.fillText(SAMPLE_TEXT, 8, 8);

  const metrics = context.measureText(SAMPLE_TEXT);
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
  let hash = 2166136261;

  for (let index = 3; index < pixels.length; index += 16) {
    hash ^= pixels[index];
    hash = Math.imul(hash, 16777619);
  }

  return {
    width: Number(metrics.width.toFixed(2)),
    hash: hash >>> 0,
  };
}

async function evaluateProbe(probe) {
  const face = [...document.fonts].find(
    (candidate) => normalizeFamily(candidate.family) === probe.family
  );
  let loaded = false;

  if (face) {
    try {
      await face.load();
      loaded = face.status === "loaded";
    } catch {
      loaded = false;
    }
  }

  await document.fonts.ready;

  const fontCheck = document.fonts.check(`48px "${probe.family}"`, SAMPLE_TEXT);
  const candidate = renderSignature(probe.family);
  const fallback = renderSignature("monospace");
  const differsFromFallback =
    candidate.hash !== fallback.hash ||
    Math.abs(candidate.width - fallback.width) > 0.1;

  return {
    ...probe,
    pass: loaded && fontCheck && differsFromFallback,
    loaded,
    fontCheck,
    candidate,
    fallback,
  };
}

function renderResult(result) {
  const container = document.querySelector(`[data-probe="${result.id}"]`);
  const status = container.querySelector("[data-status]");
  const detail = container.querySelector("[data-detail]");

  status.textContent = result.pass ? "PASS" : "FAIL";
  status.dataset.status = result.pass ? "pass" : "fail";
  detail.textContent =
    `loaded=${result.loaded}; check=${result.fontCheck}; ` +
    `width=${result.candidate.width}; fallback=${result.fallback.width}`;
}

async function run() {
  document.querySelector("#environment").textContent = navigator.userAgent;
  const results = [];

  for (const probe of PROBES) {
    const result = await evaluateProbe(probe);
    results.push(result);
    renderResult(result);
  }

  document.querySelector("#result-summary").textContent = [
    navigator.userAgent,
    ...results.map(
      (result) =>
        `${result.localName}: ${result.pass ? "PASS" : "FAIL"} ` +
        `(loaded=${result.loaded}, check=${result.fontCheck}, ` +
        `width=${result.candidate.width}, fallback=${result.fallback.width})`
    ),
  ].join("\n");
}

run();
```

- [ ] **Step 6: Run the probe regression test and verify it passes**

Run:

```bash
PYTHONPATH=. uv run --with-requirements apps/api/requirements.txt \
  pytest -p no:cacheprovider \
  apps/api/tests/test_health.py::test_web_exposes_private_local_hanzipen_probe \
  -v
```

Expected: PASS.

- [ ] **Step 7: Run static syntax and CSP checks**

Run:

```bash
node --check apps/web/font-probe.js
python3 -m json.tool apps/web/vercel.json >/dev/null
rg -n "<style|<script>" apps/web/font-probe.html
```

Expected:

- `node --check` exits 0.
- `vercel.json` parses.
- `rg` reports only the external `<script src="./font-probe.js" defer>` tag;
  there is no inline `<style>` or bare `<script>` block.

- [ ] **Step 8: Commit the isolated probe**

```bash
git add \
  apps/api/tests/test_health.py \
  apps/web/font-probe.html \
  apps/web/font-probe.css \
  apps/web/font-probe.js
git commit -m "test(web): add iOS HanziPen font probe"
```

---

### Task 3: Deploy The Probe And Record The Physical-iPhone Gate

**Files:**
- No source file changes.

- [ ] **Step 1: Run the complete local regression suite**

Run:

```bash
PYTHONPATH=. uv run --with-requirements apps/api/requirements.txt \
  pytest -p no:cacheprovider apps/api/tests
python3 -m compileall -q apps/api
node --check apps/web/app.js
node --check apps/web/font-probe.js
git diff --check
```

Expected: all 112 tests pass, syntax commands exit 0, and `git diff --check`
prints nothing.

- [ ] **Step 2: Push the probe branch**

Run:

```bash
git push origin codex/ios-font-consistency
```

Expected: `origin/codex/ios-font-consistency` advances to the probe commit without
updating `main`.

- [ ] **Step 3: Resolve the Vercel Web Preview URL**

Run:

```bash
SHA=$(git rev-parse HEAD)
DEPLOYMENT_ID=$(
  gh api "repos/aiuuu423/dayfold/deployments?sha=$SHA" \
    --jq '.[] | select(.environment == "Preview – dayfold") | .id' \
    | head -1
)
gh api "repos/aiuuu423/dayfold/deployments/$DEPLOYMENT_ID/statuses" \
  --jq '.[0] | {state, environment_url}'
```

Expected: `state` is `success` and `environment_url` is the branch's Vercel
Preview URL.

- [ ] **Step 4: Open the existing branch shareable URL on the iPhone**

In Vercel, open the successful `dayfold` deployment and use **Share → Anyone
with the link → Copy Link** if the existing up-to-date shareable URL no longer
points to the new deployment.

On the physical iPhone Safari, use the URL copied by Vercel and insert
`/font-probe` immediately before its `?_vercel_share=` query string.

Do not store the `_vercel_share` token in source, shell history, test fixtures,
or documentation.

- [ ] **Step 5: Record the visible iPhone results**

Capture one screenshot containing:

- the iPhone Safari chrome,
- all three PASS/FAIL labels,
- the rendered samples,
- the copyable summary and user-agent text.

Gate interpretation:

- `HanziPen SC: PASS` or `HanziPenSC-W3: PASS`
  - Proceed to Task 4.
- Only `HanziPenSC-W5: PASS`
  - STOP. Bold W5 cannot preserve the accepted Regular/W3 screenshot.
- All three FAIL
  - STOP. Exact matching requires a valid embedding license or a separately
    approved replacement font.

- [ ] **Step 6: Verify the macOS product baseline before any alias change**

Open the same shareable Preview root on macOS Chrome at 1440×900 and compare it
with the supplied screenshot.

Expected:

- the brand, Chinese title, navigation, input, and supporting copy retain the
  original HanziPen appearance;
- no LXGW webfont request occurs;
- there is no horizontal overflow or clipping.

---

### Task 4: Add The Passing Regular HanziPen Local Alias

> Execute this task only when `HanziPen SC` or `HanziPenSC-W3` passes in Task 3.
> If neither passes, stop the plan here without modifying product CSS.

**Files:**
- Modify: `apps/api/tests/test_health.py`
- Modify: `apps/web/styles.css:1-15`

- [ ] **Step 1: Write the failing production-alias regression**

Add this test after the baseline typography test:

```python
def test_web_maps_regular_hanzipen_local_names_without_remote_font():
    stylesheet = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")

    assert 'font-family: "Dayfold HanziPen";' in stylesheet
    assert 'local("HanziPen SC")' in stylesheet
    assert 'local("HanziPenSC-W3")' in stylesheet
    assert (
        'font-family: "Dayfold HanziPen", "HanziPen SC", "HanziPen TC", '
        '"Bradley Hand", "Klee", "PingFang SC",'
    ) in stylesheet
    assert "http://" not in stylesheet
    assert "https://" not in stylesheet
```

- [ ] **Step 2: Run the alias test and verify it fails**

Run:

```bash
PYTHONPATH=. uv run --with-requirements apps/api/requirements.txt \
  pytest -p no:cacheprovider \
  apps/api/tests/test_health.py::test_web_maps_regular_hanzipen_local_names_without_remote_font \
  -v
```

Expected: FAIL because `Dayfold HanziPen` is not defined.

- [ ] **Step 3: Add local-only aliases for weights used by the existing UI**

Insert at the top of `apps/web/styles.css`:

```css
@font-face {
  font-family: "Dayfold HanziPen";
  src: local("HanziPen SC"), local("HanziPenSC-W3");
  font-style: normal;
  font-weight: 400;
}

@font-face {
  font-family: "Dayfold HanziPen";
  src: local("HanziPen SC"), local("HanziPenSC-W3");
  font-style: normal;
  font-weight: 500;
}
```

Change only the first family in `:root`:

```css
font-family: "Dayfold HanziPen", "HanziPen SC", "HanziPen TC", "Bradley Hand",
  "Klee", "PingFang SC", sans-serif;
```

Do not add W5, remote URLs, font assets, or typography dimension changes.

- [ ] **Step 4: Run the alias and baseline tests**

Run:

```bash
PYTHONPATH=. uv run --with-requirements apps/api/requirements.txt \
  pytest -p no:cacheprovider \
  apps/api/tests/test_health.py::test_web_preserves_original_hanzipen_typography_without_webfont_override \
  apps/api/tests/test_health.py::test_web_maps_regular_hanzipen_local_names_without_remote_font \
  -v
```

Expected: both PASS.

- [ ] **Step 5: Commit and push the alias**

```bash
git add apps/api/tests/test_health.py apps/web/styles.css
git commit -m "fix(web): map iOS HanziPen local aliases"
git push origin codex/ios-font-consistency
```

- [ ] **Step 6: Verify the main page on the same physical iPhone**

Open the up-to-date shareable branch root, not `/font-probe`.

Expected:

- Chinese and Latin text match the supplied HanziPen screenshot.
- `document.fonts.check('16px "Dayfold HanziPen"', "写下今天 Dayfold")` is true.
- Today, Chat, Memory, and Growth navigation remains usable.
- The entry textarea accepts Chinese and Latin input.
- No horizontal overflow, clipping, or incoherent overlap appears.

If the main page still differs despite a passing probe, STOP. Do not add a
replacement font or alter spacing; capture the mismatch as new evidence.

---

### Task 5: Remove The Temporary Probe After Main-Page Acceptance

> Execute only after Task 4 passes physical-iPhone acceptance.

**Files:**
- Delete: `apps/web/font-probe.html`
- Delete: `apps/web/font-probe.css`
- Delete: `apps/web/font-probe.js`
- Modify: `apps/api/tests/test_health.py`

- [ ] **Step 1: Remove the temporary probe test and files**

Delete `test_web_exposes_private_local_hanzipen_probe` from
`apps/api/tests/test_health.py`.

Run:

```bash
git rm \
  apps/web/font-probe.html \
  apps/web/font-probe.css \
  apps/web/font-probe.js
```

- [ ] **Step 2: Run the production regression suite**

Run:

```bash
PYTHONPATH=. uv run --with-requirements apps/api/requirements.txt \
  pytest -p no:cacheprovider apps/api/tests
python3 -m compileall -q apps/api
node --check apps/web/app.js
git diff --check
```

Expected: 112 tests pass after adding the alias regression and removing the
temporary probe regression; syntax checks exit 0.

- [ ] **Step 3: Commit the probe cleanup**

```bash
git add apps/api/tests/test_health.py
git commit -m "chore(web): remove temporary HanziPen probe"
git push origin codex/ios-font-consistency
```

- [ ] **Step 4: Verify final branch state**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected:

- working tree is clean;
- branch tracks `origin/codex/ios-font-consistency`;
- history contains baseline restoration, probe, alias, and probe cleanup commits;
- `main` and production domains remain untouched.
