# iOS HanziPen Font Probe Design

## Status

Approved for implementation planning on 2026-11-16.

## Context

The accepted visual baseline is the supplied Dayfold screenshot rendered on
macOS with the original handwriting stack led by `HanziPen SC`. The current
branch's self-hosted LXGW WenKai Lite integration makes macOS and iOS consistent,
but changes the product's established visual character.

Apple lists HanziPen SC Regular and Bold for iOS and macOS, but the inventory
does not guarantee that Safari can resolve the family without a platform font
download. The iOS mismatch may therefore be either:

1. A CSS family-name mismatch between `HanziPen SC` and its PostScript names.
2. The font is unavailable to Safari on the test device.

The implementation must distinguish these cases before choosing a fallback.

## Decision

Restore the original Dayfold typography exactly and add an isolated diagnostic
page that tests the known HanziPen family and PostScript names on a physical
iPhone.

Do not replace the product font unless the probe proves that iOS Safari cannot
resolve any HanziPen name and the user separately approves a licensed fallback.

## Visual Source Of Truth

The supplied screenshot is authoritative for:

- Brand wordmark and Chinese handwriting character.
- Font size, weight, line height, and natural spacing.
- Typography scope across headings, navigation, form content, controls, and
  supporting copy.

No visual tuning is included in this task.

## Scope

### Restore The Baseline

- Remove the `Dayfold Hand` webfont override introduced by the current branch.
- Remove its font stylesheet link and bundled LXGW WenKai Lite assets.
- Restore the original CSS font stack led by `HanziPen SC`.
- Keep all existing font sizes, weights, line heights, colors, and layout rules.

### Add The Probe

Add a static `/font-probe.html` page that:

- Defines local-only probe families for:
  - `HanziPen SC`
  - `HanziPenSC-W3`
  - `HanziPenSC-W5`
- Tests each family against Chinese and Latin sample text.
- Displays a visible PASS/FAIL result and rendered sample for each name.
- Displays browser and platform labels only from standard user-agent data.
- Performs no network submission and stores no diagnostic result.
- Is not linked from the Dayfold product UI.

The probe must avoid false positives from fallback fonts. Each candidate is
declared through a dedicated `@font-face` using `local(...)`, then checked by
comparing rendered metrics against a controlled fallback and by using the Font
Loading API.

## Outcome Rules

### At Least One Candidate Passes

- Add only the passing family/PostScript names to the production CSS stack.
- Verify the main Dayfold page on the same iPhone.
- Remove the temporary probe page after acceptance unless retaining it is
  explicitly requested.

### All Candidates Fail

- Stop without adding an approximate product font.
- Report that exact cross-platform rendering requires either:
  - a valid HanziPen web/app embedding license, or
  - explicit approval of a different licensed font.
- Do not claim the mismatch is fixed.

## Files Expected To Change

Probe phase:

- `apps/web/font-probe.html`
- `apps/api/tests/test_health.py`
- `apps/web/index.html`
- `apps/web/styles.css`
- Remove `apps/web/assets/fonts/` from the current branch.

The final alias fix may change only `apps/web/styles.css` and the regression
test, depending on the probe result.

## Files Not To Change

- API routes and business logic.
- Authentication and user isolation.
- Database, Memory, Chat, Growth, and retrieval behavior.
- Deployment configuration and production domains.
- Existing product copy, color tokens, spacing, or responsive layout.

## Validation

1. Static regression test proves the product page no longer loads the LXGW
   replacement and the probe includes all three local names.
2. Existing API and static Web suite remains green.
3. macOS screenshot matches the supplied typography baseline.
4. Physical iPhone Safari records PASS/FAIL for all candidates.
5. If an alias passes, the main page is rechecked on the same iPhone for:
   - matching Chinese and Latin handwriting,
   - no horizontal overflow,
   - no clipping or layout shift,
   - navigation and form controls remaining usable.

## Privacy And Architecture

The probe is static and local to the browser. It sends no diagnostic data,
introduces no third-party runtime dependency, and does not affect P1 evaluation,
backend architecture, authentication, or data boundaries.

## Source

- Apple System Fonts:
  <https://developer.apple.com/fonts/system-fonts/>
