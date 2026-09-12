# Diagrams — `watermill-publisher` AWS upgrade

Generated artifacts for the Mermaid diagrams in
[`../2026-09-02-wmpub-upgrade-summary.md`](../2026-09-02-wmpub-upgrade-summary.md).

**The markdown is the single source of truth.** Nothing here is hand-maintained — edit the ` ```mermaid ` blocks in the
markdown and re-run the generators below.

## Why this folder exists

VS Code's **Markdown Preview Enhanced** renders Mermaid as a fixed-size inline SVG with **no pan and no zoom**, so the
denser architecture diagrams are unreadable at preview width. These artifacts give you a zoomable view.

## What's here

| File | What it is |
|---|---|
| `wmpub-diagrams.html` | **Self-contained zoomable viewer** — every diagram, with mouse-wheel zoom, drag-to-pan, a diagram picker, `←`/`→` navigation and *Fit* / *Reset* / *100%* buttons. Open it in a browser. Loads Mermaid + svg-pan-zoom from jsDelivr, so it needs network access on first paint |
| `NN-*.svg` | **Standalone vector renders** — open in VS Code and zoom with `Ctrl` + mouse-wheel, or in any browser. Resolution-independent, so they stay sharp at any zoom, and they work fully offline |
| `NN-*.mmd` | The extracted Mermaid source for each diagram (input to the SVG render) |
| `build-diagrams.mjs` | Extracts the Mermaid blocks from the markdown → writes the HTML viewer and the `.mmd` files. No dependencies |
| `render-svg.ps1` | Renders every `.mmd` → `.svg` via `@mermaid-js/mermaid-cli` |
| `mermaid.config.json` | Render config shared by the viewer and the SVG renderer |

## Regenerating

```powershell
# 1. viewer + .mmd sources (no install needed)
node watermill-publisher/docs/diagrams/build-diagrams.mjs

# 2. the SVGs (downloads mermaid-cli + a headless Chromium on first run)
pwsh watermill-publisher/docs/diagrams/render-svg.ps1
```

Run step 1 after **any** edit to the Mermaid blocks; run step 2 as well if you want the SVGs refreshed.

## Third option — no artifacts at all

If you just want to read a diagram in the MPE preview once, right-click the preview → **Zoom In** (or `Ctrl` `+`). That
zooms the whole document rather than the single diagram, but it is enough to make a dense diagram legible.
