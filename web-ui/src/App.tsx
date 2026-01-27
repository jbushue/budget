import React, { useState, useMemo } from 'react';
import { ApolloProvider } from '@apollo/client';
import { PaperProvider } from 'react-native-paper';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';

import client from './apolloClient';
import { lightTheme, darkTheme } from './theme';

// Screens
import Dashboard from './screens/Dashboard';
import Accounts from './screens/Accounts';
import Bills from './screens/Bills';
import Income from './screens/Income';
import Analytics from './screens/Analytics';
import Settings from './screens/Settings';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

// Dashboard Stack
function DashboardStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="DashboardScreen" component={Dashboard} />
    </Stack.Navigator>
  );
}

// Accounts Stack
function AccountsStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="AccountsScreen" component={Accounts} />
    </Stack.Navigator>
  );
}

// Bills Stack
function BillsStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="BillsScreen" component={Bills} />
    </Stack.Navigator>
  );
}

// Income Stack
function IncomeStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="IncomeScreen" component={Income} />
    </Stack.Navigator>
  );
}

// Analytics Stack
function AnalyticsStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="AnalyticsScreen" component={Analytics} />
    </Stack.Navigator>
  );
}

// Settings Stack
function SettingsStack({ isDarkMode, onToggleDarkMode }: any) {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen
        name="SettingsScreen"
        options={{
          headerShown: false,
        }}
      >
        {(props) => (
          <Settings
            {...props}
            isDarkMode={isDarkMode}
            onToggleDarkMode={onToggleDarkMode}
          />
        )}
      </Stack.Screen>
    </Stack.Navigator>
  );
}

// Main App Component
export default function App() {
  const [isDarkMode, setIsDarkMode] = useState(false);

  const theme = useMemo(() => (isDarkMode ? darkTheme : lightTheme), [isDarkMode]);

  const handleToggleDarkMode = () => {
    setIsDarkMode((prev) => !prev);
  };

  return (
    <ApolloProvider client={client}>
      <PaperProvider theme={theme}>
        <NavigationContainer>
          <Tab.Navigator
            screenOptions={({ route }) => ({
              headerShown: false,
              tabBarActiveTintColor: theme.colors.primary,
              tabBarInactiveTintColor: theme.colors.onSurfaceVariant,
              tabBarLabel:
                route.name === 'DashboardTab'
                  ? 'Dashboard'
                  : route.name === 'AccountsTab'
                  ? 'Accounts'
                  : route.name === 'BillsTab'
                  ? 'Bills'
                  : route.name === 'IncomeTab'
                  ? 'Income'
                  : route.name === 'AnalyticsTab'
                  ? 'Analytics'
                  : 'Settings',
              tabBarIcon: ({ color, size }) => {
                let iconName = 'home';
                if (route.name === 'DashboardTab') {
                  iconName = 'view-dashboard';
                } else if (route.name === 'AccountsTab') {
                  iconName = 'bank';
                } else if (route.name === 'BillsTab') {
                  iconName = 'receipt';
                } else if (route.name === 'IncomeTab') {
                  iconName = 'cash-multiple';
                } else if (route.name === 'AnalyticsTab') {
                  iconName = 'chart-box';
                } else if (route.name === 'SettingsTab') {
                  iconName = 'cog';
                }
                return (
                  <MaterialCommunityIcons name={iconName} size={size} color={color} />
                );
              },
            })}
          >
            <Tab.Screen
              name="DashboardTab"
              component={DashboardStack}
              options={{
                title: 'Dashboard',
              }}
            />
            <Tab.Screen
              name="AccountsTab"
              component={AccountsStack}
              options={{
                title: 'Accounts',
              }}
            />
            <Tab.Screen
              name="BillsTab"
              component={BillsStack}
              options={{
                title: 'Bills',
              }}
            />
            <Tab.Screen
              name="IncomeTab"
              component={IncomeStack}
              options={{
                title: 'Income',
              }}
            />
            <Tab.Screen
              name="AnalyticsTab"
              component={AnalyticsStack}
              options={{
                title: 'Analytics',
              }}
            />
            <Tab.Screen
              name="SettingsTab"
              options={{
                title: 'Settings',
              }}
            >
              {(props) => (
                <SettingsStack
                  {...props}
                  isDarkMode={isDarkMode}
                  onToggleDarkMode={handleToggleDarkMode}
                />
              )}
            </Tab.Screen>
          </Tab.Navigator>
        </NavigationContainer>
      </PaperProvider>
    </ApolloProvider>
  );
}

