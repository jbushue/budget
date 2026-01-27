import { MD3LightTheme, MD3DarkTheme } from 'react-native-paper';

export const lightTheme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: '#2E7D32',
    secondary: '#1976D2',
    tertiary: '#F57C00',
    background: '#F5F5F5',
    surface: '#FFFFFF',
    error: '#D32F2F',
    success: '#4CAF50',
    warning: '#FFC107',
    info: '#2196F3',
    // Custom colors
    positive: '#4CAF50',
    negative: '#F44336',
    neutral: '#9E9E9E',
    lightGray: '#ECEFF1',
    darkGray: '#455A64',
  },
};

export const darkTheme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    primary: '#4CAF50',
    secondary: '#42A5F5',
    tertiary: '#FFB74D',
    background: '#121212',
    surface: '#1E1E1E',
    error: '#CF6679',
    success: '#66BB6A',
    warning: '#FFA726',
    info: '#42A5F5',
    // Custom colors
    positive: '#66BB6A',
    negative: '#EF5350',
    neutral: '#616161',
    lightGray: '#37474F',
    darkGray: '#ECEFF1',
  },
};

export const globalStyles = {
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  card: {
    marginHorizontal: 12,
    marginVertical: 8,
    borderRadius: 12,
    elevation: 3,
  },
  largeTitle: {
    fontSize: 32,
    fontWeight: '700',
    color: '#212121',
    marginBottom: 8,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#212121',
    marginBottom: 16,
    marginTop: 16,
  },
  text: {
    fontSize: 14,
    color: '#424242',
  },
  textBold: {
    fontSize: 14,
    fontWeight: '600',
    color: '#212121',
  },
  smallText: {
    fontSize: 12,
    color: '#757575',
  },
  currencyText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#2E7D32',
  },
  currencyNegative: {
    fontSize: 18,
    fontWeight: '700',
    color: '#D32F2F',
  },
  padding16: {
    padding: 16,
  },
  paddingHorizontal16: {
    paddingHorizontal: 16,
  },
  marginTop16: {
    marginTop: 16,
  },
  marginBottom16: {
    marginBottom: 16,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  shadow: {
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
  },
};

