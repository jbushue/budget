# Budget App - Modern React Native Web UI

A comprehensive, feature-rich personal finance management application built with React Native, featuring real-time data visualization, budget tracking, and financial analysis.

## Features

### 📊 Dashboard
- **Net Worth Overview** - Comprehensive financial summary
- **Quick Statistics** - Bills and income at a glance
- **Bank Overview** - All accounts with current balances
- **90-Day Projection Chart** - Visual balance forecasting
- **Upcoming Bills** - Next due payments
- **Income Schedule** - Next paychecks

### 💳 Accounts Management
- Create and manage multiple banks
- Support for checking, savings, and credit accounts
- Real-time balance updates
- Interest rate tracking
- Credit card limits and available credit
- Click-to-update balances

### 📋 Bills Management
- Add fixed and recurring bills
- Multiple frequency options (weekly, monthly, quarterly, etc.)
- Visual alerts for overdue and due-soon bills
- Bill statistics and summaries
- Filter by frequency
- Next due date tracking

### 💰 Income Management
- Track multiple income sources
- Flexible frequency configurations
- Monthly and annual income calculations
- Next payment date tracking
- Annual income breakdown

### 📈 Advanced Analytics
- Balance projection charts (30, 60, 90 days)
- Income vs Expenses analysis
- Bank balance visualization
- Payment strategy insights
- Account type distribution
- Interactive charts and graphs

### 🎨 Modern UI/UX
- Clean, intuitive design
- Dark and light theme support
- Material Design 3
- Responsive layout
- Smooth animations
- Fast and performant

### 💾 Data Management
- Save to local database
- Load saved data
- Automatic synchronization
- GraphQL integration

## Installation

### Prerequisites
- Node.js 16+
- npm or yarn
- Expo CLI (for mobile): `npm install -g expo-cli`

### Setup

1. **Install Dependencies**
```bash
cd web-ui
npm install
# or
yarn install
```

2. **Configure Environment**
```bash
cp .env.example .env
```

3. **Update GraphQL Server URL** (if needed)
Edit `.env`:
```
REACT_APP_GRAPHQL_URL=http://localhost:4000/graphql
```

## Running the Application

### Web (Browser)
```bash
npm run web
# Opens http://localhost:3000
```

### iOS (with Expo)
```bash
npm run ios
# or
expo start
# Then press 'i' for iOS
```

### Android (with Expo)
```bash
npm run android
# or
expo start
# Then press 'a' for Android
```

### Start Development
```bash
npm start
# or
expo start
```

## Architecture

### Project Structure
```
src/
├── App.tsx                 # Main app with navigation
├── apolloClient.ts         # Apollo Client configuration
├── theme.ts                # Theme definitions
├── screens/                # Screen components
│   ├── Dashboard.tsx       # Home dashboard
│   ├── Accounts.tsx        # Account management
│   ├── Bills.tsx           # Bill management
│   ├── Income.tsx          # Income management
│   ├── Analytics.tsx       # Advanced analytics
│   └── Settings.tsx        # Settings & preferences
├── graphql/
│   └── queries.ts          # GraphQL queries & mutations
└── utils/
    └── formatters.ts       # Formatting utilities
```

### Tech Stack
- **Framework**: React Native
- **Navigation**: React Navigation
- **State Management**: Apollo Client
- **UI Components**: React Native Paper
- **Charts**: Victory Native
- **HTTP**: Apollo Client (GraphQL)
- **Language**: TypeScript

## Key Components

### Dashboard Screen
Real-time financial overview with charts and upcoming events.

**Features:**
- Net worth summary card
- Quick stats (bills, income)
- Bank list with balances
- 90-day projection chart
- Upcoming bills and income

### Accounts Screen
Complete account management interface.

**Features:**
- View all banks and accounts
- Create new accounts
- Update account balances
- Track credit card limits
- Interest rate management

### Bills Screen
Comprehensive bill tracking and management.

**Features:**
- Create recurring bills
- Visual due date alerts
- Frequency filtering
- Overdue indicators
- Bill statistics

### Income Screen
Income source management and projections.

**Features:**
- Add income sources
- Track payment frequency
- Calculate annual income
- View next pay dates
- Income breakdown

### Analytics Screen
Advanced financial analysis with multiple chart types.

**Features:**
- Balance projection charts
- Income vs expenses visualization
- Bank balance comparison
- Payment strategy analysis
- Discretionary fund calculations

## GraphQL Integration

The app connects to the personal finance backend GraphQL API.

### Key Queries
- `getSnapshot` - Current financial state
- `projection` - Balance projections
- `paymentPlan` - Optimized payment strategies
- `allBanks` - All bank accounts
- `allBills` - All bills
- `allIncome` - All income sources

### Key Mutations
- `createBank` - Create new bank
- `createAccount` - Create account
- `createBill` - Create bill
- `createIncomeSource` - Add income
- `updateAccountBalance` - Update balance
- `saveDatabase` - Persist data
- `loadDatabase` - Restore data

## Configuration

### Environment Variables
```bash
REACT_APP_GRAPHQL_URL        # GraphQL server URL
REACT_APP_ENV                # Environment (development/production)
REACT_APP_API_TIMEOUT        # API timeout in ms
```

### Theming
Customize theme in `src/theme.ts`:
- Light and dark theme support
- Material Design 3 colors
- Global styling

## Formatting Utilities

### Available Functions
- `formatCurrency(value)` - Format numbers as currency
- `formatDate(date)` - Format dates
- `formatPercent(value)` - Format as percentage
- `getFrequencyLabel(freq)` - Translate frequency strings
- `getDayLabel(day)` - Format day ordinals

## Development

### Adding a New Screen
1. Create file in `src/screens/`
2. Add navigation in `App.tsx`
3. Create GraphQL queries if needed

### Styling
- Use `globalStyles` from `src/theme.ts`
- React Native Paper components for UI
- Consistent spacing and colors

### Charts
- Victory Native for charts
- Responsive dimensions
- Theme-aware colors

## Performance Tips

1. **Lazy Load Screens** - Use React Navigation for optimization
2. **Memoize Components** - Use React.memo for expensive renders
3. **Efficient Queries** - Request only needed fields
4. **Cache Strategy** - Apollo Client handles caching
5. **Image Optimization** - Use native image optimization

## Troubleshooting

### GraphQL Connection Issues
- Check backend is running: `python graphql_server.py`
- Verify `REACT_APP_GRAPHQL_URL` is correct
- Check network connectivity

### Slow Performance
- Clear Apollo cache: Settings → Load from Database
- Restart development server
- Check device/emulator resources

### Build Errors
- Clear node_modules: `rm -rf node_modules && npm install`
- Clear cache: `npm cache clean --force`
- Delete `.expo` folder if using Expo

## Building for Production

### Web
```bash
npm run build
# Creates build/ directory
```

### Mobile (EAS Build)
```bash
npm install -g eas-cli
eas build --platform ios
eas build --platform android
```

## API Reference

### Dashboard Query
```graphql
query {
  snapshot {
    totalAssets
    totalLiabilities
    netWorth
    banks { ... }
    upcomingBills30Days { ... }
    upcomingIncome30Days { ... }
  }
}
```

### Create Bill Mutation
```graphql
mutation {
  createBill(
    billName: "Rent"
    amount: 1500
    dueDate: 1
    frequency: "monthly"
  ) {
    success
    message
  }
}
```

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Mobile Platform Support

- iOS 12+
- Android 5+

## Contributing

1. Follow existing code style
2. Use TypeScript for new features
3. Update documentation
4. Test on multiple platforms

## License

MIT License

## Support

For issues or questions:
1. Check documentation in main project
2. Review GraphQL API docs
3. Check console for error messages
4. Restart development server

## Additional Resources

- [React Navigation Docs](https://reactnavigation.org)
- [Apollo Client Docs](https://www.apollographql.com/docs/react)
- [React Native Paper](https://callstack.github.io/react-native-paper)
- [Victory Native](https://formidable.com/open-source/victory/docs/victory-native)
- [GraphQL Documentation](https://graphql.org/learn)

---

**Built with ❤️ for modern finance management**

