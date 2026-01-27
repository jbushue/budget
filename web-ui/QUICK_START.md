# React Native Web UI - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Install Dependencies
```bash
cd web-ui
npm install
```

### Step 2: Start GraphQL Backend
In another terminal (with uv venv activated):
```bash
cd ..  # Go to budget directory
python api_server.py
# Should output: ✓ GraphQL Playground: http://localhost:4000/graphql
```

### Step 3: Start React Native App
```bash
cd web-ui
npm start
```

The app opens at `http://localhost:3000` 🎉

## 📱 Available Screens

### Dashboard Tab
- **View**: Net worth, upcoming bills, income
- **Action**: Tap FAB to add data
- **Chart**: 90-day balance projection

### Accounts Tab
- **View**: All banks and accounts
- **Action**: Create new accounts, update balances
- **Info**: Interest rates, credit limits

### Bills Tab
- **View**: All bills with due dates
- **Action**: Create new bills
- **Features**: Overdue alerts, frequency filter

### Income Tab
- **View**: All income sources
- **Action**: Add income sources
- **Calculate**: Monthly and annual totals

### Analytics Tab
- **Charts**: Multiple data visualizations
- **Settings**: Adjust projection period (30/60/90 days)
- **Insights**: Payment strategy recommendations

### Settings Tab
- **Theme**: Toggle dark/light mode
- **Database**: Save/load data
- **Info**: App version and details

## 🔧 Configuration

### Environment Setup
```bash
# Copy example to .env
cp .env.example .env

# Update GraphQL URL if needed (default is localhost:4000)
REACT_APP_GRAPHQL_URL=http://localhost:4000/graphql
```

## 💡 Common Tasks

### Create a Bank
1. Go to **Accounts** tab
2. Tap the **+** button
3. Fill in bank details
4. Tap **Create**

### Add a Bill
1. Go to **Bills** tab
2. Tap the **+** button
3. Enter bill details:
   - Bill name
   - Amount
   - Due date (1-31)
   - Frequency
4. Tap **Create**

### Add Income
1. Go to **Income** tab
2. Tap the **+** button
3. Enter income details:
   - Source name
   - Amount
   - Pay date (1-31)
   - Frequency
4. Tap **Add**

### Update Account Balance
1. Go to **Accounts** tab
2. Tap on any account card
3. Enter new balance
4. Tap **Update**

### View Projections
1. Go to **Analytics** tab
2. Select projection period (30/60/90 days)
3. View balance forecast chart
4. See income vs expenses breakdown

### Save Data
1. Go to **Settings** tab
2. Scroll to "Data Management"
3. Tap **Save** to persist all data
4. Confirm the action

### Load Data
1. Go to **Settings** tab
2. Scroll to "Data Management"
3. Tap **Load** to restore saved data
4. Confirm the action

## 🌓 Dark Mode

Toggle dark mode in **Settings** tab:
- Tap the **Dark Mode** switch
- App theme changes immediately
- Setting is preserved

## 📊 Charts & Visualizations

The app includes multiple chart types:

- **Line Charts** - Balance projections over time
- **Bar Charts** - Bank balance comparison
- **Pie Charts** - Account distribution
- **Progress Bars** - Credit card utilization

All charts are:
- Interactive
- Theme-aware
- Responsive to screen size
- Real-time updated

## 🔄 Syncing with Backend

The app automatically syncs with the GraphQL backend:

1. **Save**: All changes persist to database
2. **Load**: Restore previously saved data
3. **Refresh**: Pull latest data from server
4. **Real-time**: Charts update instantly

## ⚠️ Troubleshooting

### "Cannot connect to GraphQL server"
- Check backend is running: `python graphql_server.py`
- Verify URL in `.env`
- Check firewall/network settings

### "No data appears"
- Make sure you've created banks/accounts first
- Tap refresh button in screen header
- Go to Settings and tap "Load" to restore data

### "Slow performance"
- Clear Apollo cache by loading database
- Restart development server
- Check device/emulator resources
- Close other applications

### "Charts not showing"
- Make sure you have data (create banks/bills/income)
- Check console for errors (F12)
- Refresh the page

## 🎨 Customization

### Change Theme Colors
Edit `src/theme.ts`:
```typescript
export const lightTheme = {
  colors: {
    primary: '#2E7D32',  // Change this
    secondary: '#1976D2',  // Or this
    // ...
  }
}
```

### Add New Screen
1. Create `src/screens/MyScreen.tsx`
2. Add to `App.tsx` navigation
3. Add tab button in bottom tab navigator

### Modify Layout
- Edit screen files in `src/screens/`
- Use React Native components
- Apply `globalStyles` from `theme.ts`

## 📚 Documentation

Full documentation available in:
- `README.md` - Complete feature guide
- Parent project docs - Backend details
- GraphQL API docs - Query reference

## 🚢 Deployment

### Web (Browser)
```bash
npm run build
# Upload 'build' folder to hosting
```

### Mobile (iOS)
```bash
expo build:ios
# Follow prompts to build
```

### Mobile (Android)
```bash
expo build:android
# Follow prompts to build
```

## 🆘 Need Help?

1. **Check Docs** - See README.md
2. **Check Backend** - Is GraphQL server running?
3. **Check Console** - Any error messages? (F12)
4. **Restart** - Clear cache, restart server
5. **Check Network** - Can you reach http://localhost:4000?

## ✨ Tips & Tricks

- **Quick Refresh**: Swipe down on any screen to refresh data
- **Quick Update**: Tap any account to update its balance
- **View Details**: Tap any bill/income for more info
- **Dark Mode**: Use for reduced eye strain
- **Projection**: Change days to see different time periods
- **Export**: View reports in parent CLI app

## 🎯 Next Steps

1. ✅ Install and run the app
2. ✅ Create banks and accounts
3. ✅ Add bills and income
4. ✅ View projections and analytics
5. ✅ Save your data
6. ✅ Customize theme if desired
7. ✅ Explore all screens and features

---

**You're all set! Start managing your finances with the modern Budget App UI!** 🎉

For issues: Check the parent project documentation or GraphQL API docs.

