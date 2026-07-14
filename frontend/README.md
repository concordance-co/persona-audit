# Frontend

React + Vite dashboard. `npm install && npm run dev` (backend on :8100 is
proxied via `vite.config.js`); `npm run build` for a production bundle.

## Map

```text
src/main.jsx / App.jsx           entry; App renders the route table
src/api.js                       every backend call (thin fetch wrappers)
src/hooks/useAsyncResource.js    fetch-on-mount hook: {data, error} + deps
src/routes/BehaviorAuditRoutes.jsx  route table only (~45 lines)
src/routes/behavior/
  layout.jsx                     Shell (sidebar/nav), provider selection
  helpers.js                     data shaping: score-row -> chart series, fmt/pct
  shared.jsx                     labels, pills, hints, small formatters
  charts.jsx                     overview/system charts (baselines, outliers)
  tracks.jsx                     Sol/Marrow/control comparison components
  panels.jsx                     analytics + session drilldown panels
  pages/                         one file per route (Overview, Character, Tail,
                                 Sessions, SessionDetail, Report, Registry, ...)
src/styles.css                   all styling (plain CSS, class-per-component)
```

## How data flows

1. A page component calls `useAsyncResource(() => getX(params, provider), [deps])`
   with `getX` from `src/api.js`; every endpoint accepts `?provider=`.
2. The active provider comes from `useProviderSelection()` (`behavior/layout.jsx`):
   URL `?provider=` first, then localStorage, defaulting to `tau2`.
3. **Payloads drive the UI.** Report-shaped payloads embed a `provider` block —
   the backend descriptor (`backend/api/providers/<key>.py`) whose `copy` and
   `features` keys control page text and which panels render. Prefer adding a
   descriptor feature flag over hardcoding provider checks.
4. Score-derived views key off `score_family` + `coordinate` on score rows;
   the shaping lives in `behavior/helpers.js`.

## Remixing

- **New view of existing data:** add a component in the closest section file
  (or a new one), compose payload fields, wire it into a page under
  `behavior/pages/`. Styling is plain CSS classes in `src/styles.css`.
- **New page:** create `behavior/pages/YourPage.jsx`, add a `<Route>` in
  `BehaviorAuditRoutes.jsx`, and a nav entry in `behavior/layout.jsx`.
- **New endpoint:** add the wrapper in `src/api.js` next to its siblings.
- **New scoring space:** the backend side is `docs/add-a-scoring-space.md`;
  rows for a new `score_family` already flow through the generic score
  payloads — a dedicated view is just a new component over them.

Charts are [recharts](https://recharts.org/); follow the existing chart
components in `charts.jsx` / `tracks.jsx` for conventions (colors, tooltips,
`ResponsiveContainer` sizing).

## Verify

`npm run build` must pass. There is no JS test suite (by design — the backend
API tests pin the payload contracts); for visual changes run the app and check
the affected pages against both `tau2` and `persona_demo` providers.
