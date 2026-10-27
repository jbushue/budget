# Budget Manager Web UI

Modern Vue 3 + TypeScript web interface for the Personal Finance Management System.

## Tech Stack

- **Vue 3** with Composition API + `<script setup>`
- **TypeScript** for type safety
- **Vite** for fast dev & build
- **Apollo Client** for GraphQL communication
- **Chart.js** + vue-chartjs for projections
- **Vue Router** for SPA navigation
- **date-fns** for date formatting

## Quick Start

### 1. Start the API server

```bash
cd ..
python api_server.py
# Runs on http://localhost:4000
```

### 2. Start the web UI

```bash
npm install
npm run dev
# Opens on http://localhost:3000
```

The dev server proxies `/graphql` and `/health` to `localhost:4000`.

## Pages

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | Financial overview with KPIs, bank summaries, upcoming events, 90-day chart |
| Accounts | `/accounts` | Manage banks, checking/savings/credit accounts, update balances |
| Bills | `/bills` | View and add bills (fixed/variable), filter by type/frequency |
| Income | `/income` | Manage income sources with semimonthly support and distributions |
| Timeline | `/timeline` | Balance projection chart, calendar view, configurable 30-365 days |
| Optimizer | `/optimizer` | Payment optimization, schedule, action items, warnings |
| Settings | `/settings` | Database save/load, API health check |

## Build for Production

```bash
npm run build
# Output in dist/
```
