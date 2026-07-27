# Remixing Persona Audit Views

The dashboard is meant to be recomposed. Providers supply normalized traces,
score rows, labels, copy, feature flags, analytics dimensions, and an optional
Character reference. React pages decide how to present those payloads.

## Before Editing A View

1. Run the backend and inspect the payload you intend to use:

   ```bash
   curl "http://localhost:8100/api/audit/product-analytics?provider=local"
   curl "http://localhost:8100/api/audit/character?provider=local"
   curl "http://localhost:8100/api/audit/tail?provider=local"
   ```

2. Keep provider-specific parsing and grouping out of React. Put source
   parsing in the adapter and grouping paths on `ProviderSpec.dimensions`.
3. Treat scores as investigation signals, not probabilities or verdicts.

## Add A Card To Overview

- Page composition: `frontend/src/routes/behavior/pages/Overview.jsx`
- Reusable charts: `frontend/src/routes/behavior/charts.jsx`
- Analytics panels: `frontend/src/routes/behavior/panels.jsx`
- Track comparison components: `frontend/src/routes/behavior/tracks.jsx`
- Payload: `GET /api/audit/product-analytics?provider=<key>`

Compose a small component from an existing payload field, add it to Overview,
and gate it with data availability or a provider feature—not a provider-name
check.

## Add A Page

1. Create `frontend/src/routes/behavior/pages/YourPage.jsx`.
2. Fetch through a wrapper in `frontend/src/api.js`; every provider-aware
   endpoint should receive the selected provider.
3. Add the route in `frontend/src/routes/BehaviorAuditRoutes.jsx`.
4. Add navigation in `frontend/src/routes/behavior/layout.jsx`.
5. Run `cd frontend && npm run build`.

## Visualize A New Score Family

Generic score rows use `score_family`, `coordinate`, `trace_id`, `turn_index`,
and `score`. New families automatically appear in score inventory and session
detail payloads. For a dedicated view:

1. Add a backend view model only if the chart needs aggregation not already in
   `/api/audit/report`, `/api/audit/product-analytics`, or session detail.
2. Keep SQL/offline aggregation shapes in parity.
3. Build a component over the generic coordinate rows.
4. Add provider descriptor copy or a feature flag if the page is optional.

Character and Tail specifically consume assistant-axis trait coordinates.
Character uses the provider's configured comparison reference, while Tail
uses the audited provider's own distribution.

## Verification

Check the changed page with `persona_demo`, `local` (including an unscored
file), and any provider whose feature flags differ. Then run:

```bash
uv run pytest
cd frontend && npm run build
```
