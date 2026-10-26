# Lumen dashboard

React 19 + Vite 7, with Recharts and Lucide icons. Product calculations, findings,
documents, usage and exports come from FastAPI. The built-in saved examples are
real, timestamped prior AI reviews and are labeled.

Run `npm ci` and `npm run build`, then start the backend from the project root.
FastAPI serves the dashboard at localhost:8000. For development, `npm run dev`
proxies API requests to the backend. No secret belongs in a Vite variable.

`npm run test:e2e` runs the real-backend browser suite; `E2E_LIVE=1` additionally
spends tokens on a fresh uploaded review. See the root README for Windows commands
and project-local Chromium installation.

`main.jsx` manages navigation/jobs; `views.jsx` implements review views;
`PremiumChart.jsx` displays Python-calculated dollar contributions; `ui.jsx`
contains formatting, API and accessible dialog helpers; `styles.css` defines the
responsive black-and-pink theme. Use `npx prettier --write src e2e` after edits.
