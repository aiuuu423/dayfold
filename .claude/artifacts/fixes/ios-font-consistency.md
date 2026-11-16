# Bug: iOS Chinese text does not match the Dayfold handwriting style

> Status: FIXED
> Mode: default
> Severity: minor
> Author: Dayfold
> Last updated: 2026-11-16

## Symptom

Dayfold uses a handwriting-style font stack, but Chinese text renders differently
between macOS and iOS Safari. macOS can resolve `HanziPen SC`; iOS falls back to
`PingFang SC` for Chinese glyphs while Latin glyphs can still use a handwriting
font.

## Expected

The production Web UI should use the same licensed handwriting font for Chinese
and Latin text on desktop and mobile, without depending on fonts installed on the
device.

## Reproduction

- Steps: open the same Dayfold build on macOS and iOS and compare Chinese text.
- Test location: `apps/api/tests/test_health.py:126`
- Reproduction stability: 3/3 reliably failed before the font assets were added.

## Hypotheses & diagnosis

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | The CSS stack depends on a macOS-only Chinese handwriting font. | confirmed | `styles.css` listed `HanziPen SC` first but shipped no Web font; screenshots showed Chinese-only fallback on iOS. |
| H2 | Safari text autosizing or responsive CSS changes the font. | eliminated | The mismatch followed glyph coverage, while font sizes and layout rules were shared across viewports. |

## Root cause

The UI declared local font family names but did not ship a Chinese handwriting
Web font. Font resolution therefore depended on each operating system's installed
fonts, and iOS used a different fallback for Chinese glyphs.

## Fix

- `apps/web/index.html`: load the self-hosted font stylesheet before the app CSS.
- `apps/web/styles.css`: make `Dayfold Hand` the first UI font family.
- `apps/web/assets/fonts/`: add LXGW WenKai Lite Regular as 97 Unicode-range
  WOFF2 subsets, its SIL Open Font License, and source notice.
- `apps/api/tests/test_health.py`: assert that the font is local, licensed, uses
  `font-display: swap`, and has no missing or remote assets.

The original local font stack remains as a loading-failure fallback.

## Verification

- V-1: regression test with the fix present -> GREEN.
- V-2: temporarily remove the font integration -> regression test returns RED.
- V-3: restore the integration -> regression test returns GREEN.
- V-4: API and static Web test suite -> 111 passed.
- V-5: Playwright at 390x844, 414x896, and 1440x900 -> 3 passed; font ready,
  no horizontal overflow, no console errors, and all requested font subsets 200.
- V-6: visual inspection of mobile and desktop screenshots -> no clipping,
  overlap, or unintended layout shift.

Real iPhone Safari remains a release-environment acceptance check because the
automated browser run used system Chrome with iPhone-sized viewports.

## Regression test

- Path: `apps/api/tests/test_health.py:126`
- Name: `test_web_self_hosts_chinese_handwriting_font`

## Pattern analysis

| Search method | Hits | Same risk in current production Web |
|---|---:|---|
| `rg -n --glob '*.{css,html,js,jsx,ts,tsx}' 'font-family\|HanziPen\|PingFang\|Bradley Hand\|Klee' .` | 2 historical product prototypes plus reports/docs | No |

The same local-only product font stack remains in
`docs/mvp/Life-Companion-MVP-Interactive-Prototype.html` and
`docs/mvp/legacy-prototype/life-companion-mvp-design.html`. These are historical
prototype artifacts, not the deployed `apps/web` runtime, so they are not changed
in this surgical fix.

## Open questions / Follow-ups

- Validate the preview or production build on a physical iPhone Safari before
  release sign-off.
