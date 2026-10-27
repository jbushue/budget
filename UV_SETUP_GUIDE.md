# Setup Guide (uv)

How to set up and run Budget Manager with [uv](https://docs.astral.sh/uv/), the Python package and environment manager. If you'd rather use plain `pip`, see the [README](README.md#manual-start). On Windows you can also just double-click **`start.bat`**.

The app has two parts:

| Part | What it is | Address |
|---|---|---|
| API server | Python (Flask + GraphQL) with a SQLite database | http://127.0.0.1:4000 |
| Web interface | Vue 3 + Vite | http://localhost:3000 |

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Python 3.13+ (uv can install it for you: `uv python install 3.13`)
- Node.js 20+ (includes `npm`)

---

## One-time setup

Run these from the project folder (the one containing `pyproject.toml`).

```bash
# 1. Python: creates .venv and installs everything in pyproject.toml (incl. pytest)
uv sync

# 2. Web interface
cd web-ui
npm install
cd ..
```

`uv sync` creates a `uv.lock` file the first time. Keep it if you want everyone to get exactly the same package versions.

Check it worked:

```bash
uv run python -c "from models.graphql_schema import schema; print('API OK')"
```

> **If `.venv` is broken** (for example, errors about a missing `python313.dll` after a Python upgrade), delete the `.venv` folder and run `uv sync` again.

---

## Running the app

You need two terminals.

**Terminal 1 — API server**
```bash
uv run api_server.py
```
You should see the server start on port 4000. `uv run` uses the project's `.venv` automatically, so there's no need to activate it.

**Terminal 2 — web interface**
```bash
cd web-ui
npm run dev
```

Then open **http://localhost:3000**. The web interface forwards its API calls to port 4000, so that's the only address you need.

Stop either one with **Ctrl+C**.

**Optional — command-line menu**
```bash
uv run cli.py
```
A text menu with: Dashboard & Overview, Views & Projections, Planning & Optimization, Manage Data, Reports & Export, and Database & File Management (including Excel import/export and the import template).

---

## Useful addresses

| Address | What's there |
|---|---|
| http://localhost:3000 | The web interface — see the [User Guide](docs/USER_GUIDE.md) |
| http://127.0.0.1:4000/graphql | GraphQL playground: explore and try the API |
| http://127.0.0.1:4000/health | Quick status check (counts of banks, bills, income) |

Your data is stored in `~/.budget_app/finance.db` (Windows: `C:\Users\<you>\.budget_app\finance.db`). Copy that file to back it up.

Server options (set before `uv run api_server.py`):

| Variable | Default | Purpose |
|---|---|---|
| `BUDGET_HOST` | `127.0.0.1` | Listen address. The API has no login — only change this if you understand the risk. |
| `BUDGET_DEBUG` | off | `1` turns on Flask debug mode. |

---

## Common commands

```bash
# Python
uv sync                     # install / update dependencies from pyproject.toml
uv add <package>            # add a dependency (updates pyproject.toml and uv.lock)
uv run pytest               # run the test suite (uses a temporary database, never your real data)
uv run python example.py    # library demo

# Web interface (from web-ui/)
npm run dev                 # development server on port 3000
npm run build               # type-check (vue-tsc) and production build into web-ui/dist
npm run preview             # serve the production build
```

---

## Troubleshooting

**The web page loads but shows errors or no data**
The API server isn't running or isn't reachable. Start it in Terminal 1 and check http://127.0.0.1:4000/health.

**`ModuleNotFoundError` (flask, graphene, …)**
Run `uv sync`, and start the server with `uv run api_server.py` (not a bare `python` from another environment).

**Port 3000 or 4000 already in use**
Another copy is probably still running. Close it, or find and stop the process:
```bash
# Windows
netstat -ano | findstr :4000
taskkill /PID <pid> /F

# macOS / Linux
lsof -i :4000
kill <pid>
```

**`npm install` fails**
Delete `web-ui/node_modules` and run `npm install` again. Make sure Node.js is version 20 or newer (`node --version`).

**Something else**
See the Troubleshooting & FAQ section of the [User Guide](docs/USER_GUIDE.md).
