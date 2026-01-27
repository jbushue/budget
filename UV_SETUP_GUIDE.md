# 🚀 Complete Setup Guide - Using uv Virtual Environment

## ✅ Status: Everything is Ready!

Your Personal Finance Management System is fully configured with:
- ✓ Python backend with GraphQL API
- ✓ React Native web UI with npm
- ✓ SQLite database for persistence
- ✓ All dependencies installed
- ✓ API server (renamed to `api_server.py`)

---

## 📋 Prerequisites

- `uv` installed (Python package manager with virtual env)
- `npm` installed (Node.js package manager)
- `python` 3.13+
- `node` 16+

---

## 🛠️ Initial Setup (One Time Only)

### 1. Create and Activate uv Virtual Environment

```bash
cd /Users/justin/PycharmProjects/budget

# Create uv virtual environment (if not already done)
uv venv

# Activate the environment
source .venv/bin/activate
# On Windows: .venv\Scripts\activate

# Verify activation (you should see (budget) in your prompt)
```

### 2. Install Python Dependencies

```bash
# Install required packages
uv pip install flask flask-cors graphene sqlalchemy openpyxl reportlab

# Verify Flask works
python -c "from flask import Flask; print('✓ Flask OK')"

# Verify GraphQL works
python -c "from models.graphql_schema import schema; print('✓ GraphQL OK')"
```

### 3. Install Node Dependencies

```bash
cd web-ui

# Install React dependencies
npm install --legacy-peer-deps

# Verify npm is ready
npm list --depth=0 | head -5
```

---

## ⚡ Quick Start (Every Time You Code)

### Terminal 1: Start the GraphQL Backend

```bash
cd /Users/justin/PycharmProjects/budget

# Activate uv environment (if not already active)
source .venv/bin/activate

# Start the API server
python api_server.py
```

**Expected output:**
```
================================================================================
🏦 PERSONAL FINANCE GRAPHQL API SERVER
================================================================================

📍 Starting GraphQL server...

✓ GraphQL Playground: http://localhost:4000/graphql
✓ Health Check: http://localhost:4000/health
✓ API Info: http://localhost:4000/

================================================================================
```

### Terminal 2: Start the React Web UI

```bash
cd /Users/justin/PycharmProjects/budget/web-ui

# Start development server
npm start
```

**Expected output:**
```
Compiled successfully!

You can now view budget-app in the browser.

  Local:            http://localhost:3000
  On Your Network:  http://192.168.x.x:3000
```

### Terminal 3 (Optional): Use the CLI

```bash
cd /Users/justin/PycharmProjects/budget

# Activate uv environment
source .venv/bin/activate

# Start interactive CLI
python cli.py
```

---

## 📋 Common Commands with uv

### Virtual Environment

```bash
# Activate venv
source .venv/bin/activate

# Deactivate venv
deactivate

# Check if activated (should show (budget) in prompt)
which python

# List installed packages
uv pip list

# Install a package
uv pip install package_name

# Install from requirements.txt
uv pip install -r requirements.txt
```

### API Server

```bash
# Start server
python api_server.py

# Server endpoints:
# - Playground: http://localhost:4000/graphql
# - Health: http://localhost:4000/health
# - Info: http://localhost:4000/

# Stop server: Press Ctrl+C
```

### Web UI

```bash
cd web-ui

# Start development
npm start

# Build for production
npm run build

# Run tests
npm test

# Clean reinstall
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

### CLI

```bash
# Start interactive menu
python cli.py

# From menu, you can:
# 1. View financial snapshot
# 2. Update account balance
# 3. Project balances
# 4. View bills & income
# 5. Get payment optimization
# 6. Add promotional offers
# 7. Generate reports
# 8. Create banks & accounts
# 9. Add bills & income
# 10. Save/Load database
```

---

## 🌐 Accessing Your App

Once both terminals are running:

### Web UI (Dashboard)
```
http://localhost:3000
```
- View financial snapshot
- Create banks & accounts
- Add bills & income
- View analytics & projections
- Toggle dark/light mode

### GraphQL Playground
```
http://localhost:4000/graphql
```
- Interactive GraphQL IDE
- Write and test queries
- Explore schema
- View documentation

### Health Check
```
http://localhost:4000/health
```
JSON response with current data stats

---

## 📁 Project Structure

```
budget/
├── .venv/                    ← Your uv virtual environment
├── api_server.py             ← GraphQL API server
├── cli.py                    ← CLI interface
├── models/                   ← Business logic
│   ├── graphql_schema.py     ← GraphQL definitions
│   ├── finance_manager.py
│   ├── database.py
│   └── ...
├── web-ui/                   ← React Native web app
│   ├── src/
│   │   ├── App.tsx
│   │   ├── screens/
│   │   ├── graphql/
│   │   └── utils/
│   ├── package.json
│   ├── .npmrc                ← npm config (legacy-peer-deps)
│   └── node_modules/
└── ...
```

---

## 🔧 Troubleshooting

### "Command 'source' not found"
→ You're on Windows. Use: `.venv\Scripts\activate`

### "python: command not found"
→ Make sure venv is activated: `source .venv/bin/activate`

### "ModuleNotFoundError: No module named 'flask'"
→ Install dependencies: `uv pip install flask flask-cors`

### "Cannot connect to localhost:4000"
→ Make sure API server is running in Terminal 1

### "npm ERR! code ERESOLVE"
→ Use legacy-peer-deps: `npm install --legacy-peer-deps`

### "Port 3000 already in use"
```bash
# Find and kill process
lsof -i :3000
kill -9 <PID>
```

### "Port 4000 already in use"
```bash
# Find and kill process
lsof -i :4000
kill -9 <PID>
```

### "GraphQL queries not working"
→ Check playground at http://localhost:4000/graphql
→ Try sample query from GRAPHQL_API.md

---

## 📊 Typical Workflow

### Day 1: Initial Setup
```bash
# One-time setup
uv venv
source .venv/bin/activate
uv pip install flask flask-cors graphene sqlalchemy openpyxl reportlab
cd web-ui
npm install --legacy-peer-deps
cd ..
```

### Daily: Start Development
```bash
# Terminal 1
source .venv/bin/activate
python api_server.py

# Terminal 2
cd web-ui
npm start

# Terminal 3 (optional)
source .venv/bin/activate
python cli.py
```

### When Done
```bash
# Stop servers: Press Ctrl+C in each terminal
# Deactivate venv:
deactivate
```

---

## ✨ Features Available

### Web UI (http://localhost:3000)
- ✓ Dashboard with net worth & charts
- ✓ Account management
- ✓ Bill tracking
- ✓ Income management
- ✓ Advanced analytics
- ✓ Dark/light theme
- ✓ Database save/load

### GraphQL API (http://localhost:4000/graphql)
- ✓ 9 queries for financial data
- ✓ 7 mutations for data creation
- ✓ Real-time synchronization
- ✓ Interactive playground
- ✓ Complete documentation

### CLI (Terminal)
- ✓ Interactive menu system
- ✓ 13 main menu options
- ✓ Complete financial management
- ✓ Report generation
- ✓ Excel/PDF export

---

## 📖 Documentation Files

- **QUICK_START.md** (this file) - Setup guide
- **README.md** - Complete feature guide
- **GRAPHQL_API.md** - API reference
- **cli.py** - Interactive menu (run it!)
- **api_server.py** - GraphQL server (run it!)

---

## ✅ You're All Set!

Now run:

### Terminal 1
```bash
source .venv/bin/activate
python api_server.py
```

### Terminal 2
```bash
cd web-ui
npm start
```

Then open **http://localhost:3000** and start managing your finances! 🎉

---

## 🆘 Need Help?

1. **Check Console** - Look for error messages (F12 in browser)
2. **Check Server** - Is api_server.py running?
3. **Check Venv** - Is `(budget)` showing in your prompt?
4. **Check Network** - Can you reach http://localhost:4000?
5. **Read Docs** - Check README.md for features

---

**Happy coding!** 💰📊✨

