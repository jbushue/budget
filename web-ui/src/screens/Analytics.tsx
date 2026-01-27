import React, { useState } from 'react';
import {
  ScrollView,
  StyleSheet,
  View,
  Dimensions,
} from 'react-native';
import {
  Card,
  Text,
  useTheme,
  Appbar,
  SegmentedButtons,
  Snackbar,
} from 'react-native-paper';
import { useQuery } from '@apollo/client';
import {
  VictoryBar,
  VictoryLine,
  VictoryChart,
  VictoryAxis,
  VictoryPie,
  VictoryLegend,
} from 'victory-native';
import { GET_SNAPSHOT, GET_PROJECTION, GET_PAYMENT_PLAN, GET_ALL_BILLS, GET_ALL_INCOME } from '../graphql/queries';
import { globalStyles } from '../theme';
import { formatCurrency, formatPercent } from '../utils/formatters';

const { width } = Dimensions.get('window');

interface AnalyticsScreenProps {
  navigation: any;
}

const AnalyticsScreen: React.FC<AnalyticsScreenProps> = ({ navigation }) => {
  const theme = useTheme();
  const [projectionDays, setProjectionDays] = useState('90');
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  const { data: snapshotData } = useQuery(GET_SNAPSHOT);
  const { data: projectionData } = useQuery(GET_PROJECTION, {
    variables: { days: parseInt(projectionDays) },
  });
  const { data: paymentPlanData } = useQuery(GET_PAYMENT_PLAN, {
    variables: { days: parseInt(projectionDays) },
  });
  const { data: billsData } = useQuery(GET_ALL_BILLS);
  const { data: incomeData } = useQuery(GET_ALL_INCOME);

  const snapshot = snapshotData?.snapshot;
  const projection = projectionData?.projection;
  const paymentPlan = paymentPlanData?.paymentPlan;

  // Prepare chart data
  const bankChartData = snapshot?.banks?.map((bank: any, idx: number) => ({
    x: bank.name,
    y: bank.totalBalance,
  })) || [];

  const projectionChartData = projection?.snapshots?.slice(0, parseInt(projectionDays)).map((snap: any) => ({
    x: new Date(snap.date).getDate(),
    y: snap.total,
  })) || [];

  // Calculate account type distribution
  const accountTypeData = [
    { x: 'Bank Accounts', y: snapshot?.banks?.reduce((sum: number, b: any) => sum + b.bankAccounts.length, 0) || 0 },
    { x: 'Credit Cards', y: snapshot?.banks?.reduce((sum: number, b: any) => sum + b.creditAccounts.length, 0) || 0 },
  ];

  // Calculate asset distribution
  const assetDistribution = snapshot?.banks?.map((bank: any) => ({
    x: bank.name,
    y: bank.totalBalance,
  })) || [];

  // Bill breakdown by frequency
  const billsData = (billsData?.allBills || []).reduce((acc: any, bill: any) => {
    const found = acc.find((b: any) => b.x === bill.frequency);
    if (found) {
      found.y += 1;
    } else {
      acc.push({ x: bill.frequency, y: 1 });
    }
    return acc;
  }, []);

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
      <Appbar.Header>
        <Appbar.Content title="Analytics" />
      </Appbar.Header>

      <ScrollView style={styles.scrollView}>
        {/* Net Worth Overview */}
        <Card style={[globalStyles.card, { backgroundColor: theme.colors.primary }]}>
          <Card.Content>
            <View style={globalStyles.row}>
              <View>
                <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12 }}>Net Worth</Text>
                <Text style={{ color: '#FFF', fontSize: 28, fontWeight: '700', marginTop: 4 }}>
                  {formatCurrency(snapshot?.netWorth || 0)}
                </Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12 }}>Assets vs Liabilities</Text>
                <Text style={{ color: '#FFF', fontSize: 14, marginTop: 8 }}>
                  {formatCurrency(snapshot?.totalAssets || 0)} / {formatCurrency(snapshot?.totalLiabilities || 0)}
                </Text>
              </View>
            </View>
          </Card.Content>
        </Card>

        {/* Projection Settings */}
        <View style={[globalStyles.paddingHorizontal16, { marginVertical: 12 }]}>
          <Text style={globalStyles.textBold}>Projection Period</Text>
          <SegmentedButtons
            value={projectionDays}
            onValueChange={setProjectionDays}
            buttons={[
              { value: '30', label: '30 Days' },
              { value: '60', label: '60 Days' },
              { value: '90', label: '90 Days' },
            ]}
            style={{ marginTop: 8 }}
          />
        </View>

        {/* Balance Projection Chart */}
        {projectionChartData.length > 0 && (
          <Card style={globalStyles.card}>
            <Card.Content>
              <Text style={globalStyles.sectionTitle}>Balance Projection</Text>
              <VictoryChart width={width - 40} height={280}>
                <VictoryAxis
                  dependentAxis
                  tickFormat={(t: number) => `$${(t / 1000).toFixed(0)}k`}
                  style={{
                    grid: { stroke: '#e0e0e0', strokeWidth: 0.5 },
                  }}
                />
                <VictoryAxis
                  label="Days"
                  style={{
                    grid: { stroke: '#e0e0e0', strokeWidth: 0.5 },
                  }}
                />
                <VictoryLine
                  data={projectionChartData}
                  style={{
                    data: { stroke: theme.colors.primary, strokeWidth: 2.5 },
                    parent: { border: '1px solid #ccc' },
                  }}
                  interpolation="natural"
                />
              </VictoryChart>
              <View style={[globalStyles.row, { marginTop: 12 }]}>
                <View>
                  <Text style={globalStyles.smallText}>Projected Balance</Text>
                  <Text style={[globalStyles.currencyText, { fontSize: 16 }]}>
                    {formatCurrency(projection?.totalFinalBalance || 0)}
                  </Text>
                </View>
                <View>
                  <Text style={globalStyles.smallText}>Net Change</Text>
                  <Text
                    style={[
                      globalStyles.currencyText,
                      { fontSize: 16, color: (projection?.netChange || 0) > 0 ? '#4CAF50' : '#D32F2F' },
                    ]}
                  >
                    {(projection?.netChange || 0) > 0 ? '+' : ''}{formatCurrency(projection?.netChange || 0)}
                  </Text>
                </View>
              </View>
            </Card.Content>
          </Card>
        )}

        {/* Income vs Expenses */}
        <Card style={globalStyles.card}>
          <Card.Content>
            <Text style={globalStyles.sectionTitle}>Income vs Expenses</Text>
            <View style={[globalStyles.row, { marginVertical: 12 }]}>
              <View>
                <Text style={globalStyles.smallText}>Total Income</Text>
                <Text style={[globalStyles.currencyText, { color: theme.colors.success, fontSize: 18 }]}>
                  +{formatCurrency(projection?.totalIncome || 0)}
                </Text>
              </View>
              <View>
                <Text style={globalStyles.smallText}>Total Expenses</Text>
                <Text style={[globalStyles.currencyNegative, { fontSize: 18 }]}>
                  -{formatCurrency(projection?.totalExpenses || 0)}
                </Text>
              </View>
            </View>
            {projection && (
              <>
                <View style={{ height: 6, backgroundColor: '#E0E0E0', borderRadius: 3, marginBottom: 8 }}>
                  <View
                    style={{
                      height: 6,
                      backgroundColor: theme.colors.success,
                      width: `${Math.min(100, (projection.totalIncome / (projection.totalIncome + projection.totalExpenses)) * 100)}%`,
                      borderRadius: 3,
                    }}
                  />
                </View>
                <View style={globalStyles.row}>
                  <Text style={globalStyles.smallText}>
                    Income: {formatPercent((projection.totalIncome / (projection.totalIncome + projection.totalExpenses)) * 100)}
                  </Text>
                  <Text style={globalStyles.smallText}>
                    Expenses: {formatPercent((projection.totalExpenses / (projection.totalIncome + projection.totalExpenses)) * 100)}
                  </Text>
                </View>
              </>
            )}
          </Card.Content>
        </Card>

        {/* Banks Overview Chart */}
        {bankChartData.length > 0 && (
          <Card style={globalStyles.card}>
            <Card.Content>
              <Text style={globalStyles.sectionTitle}>Bank Balances</Text>
              <VictoryChart width={width - 40} height={250}>
                <VictoryAxis />
                <VictoryAxis dependentAxis tickFormat={(t: number) => `$${(t / 1000).toFixed(0)}k`} />
                <VictoryBar
                  data={bankChartData}
                  style={{
                    data: {
                      fill: theme.colors.primary,
                      width: 40,
                    },
                  }}
                />
              </VictoryChart>
            </Card.Content>
          </Card>
        )}

        {/* Payment Plan Insights */}
        {paymentPlan && (
          <Card style={globalStyles.card}>
            <Card.Content>
              <Text style={globalStyles.sectionTitle}>Payment Strategy</Text>
              <View style={[globalStyles.row, { marginVertical: 12 }]}>
                <View>
                  <Text style={globalStyles.smallText}>Discretionary Funds</Text>
                  <Text style={[globalStyles.currencyText, { fontSize: 18 }]}>
                    {formatCurrency(paymentPlan.discretionaryFunds)}
                  </Text>
                </View>
                <View>
                  <Text style={globalStyles.smallText}>Total Interest</Text>
                  <Text style={[globalStyles.currencyNegative, { fontSize: 18 }]}>
                    {formatCurrency(paymentPlan.totalInterest)}
                  </Text>
                </View>
              </View>
              {paymentPlan.violations?.length > 0 && (
                <View style={{ marginTop: 12, padding: 8, backgroundColor: '#FFEBEE', borderRadius: 8 }}>
                  <Text style={{ color: '#D32F2F', fontWeight: '600', marginBottom: 4 }}>Issues Detected:</Text>
                  {paymentPlan.violations.map((violation: string, idx: number) => (
                    <Text key={idx} style={{ color: '#D32F2F', fontSize: 12, marginVertical: 2 }}>
                      • {violation}
                    </Text>
                  ))}
                </View>
              )}
            </Card.Content>
          </Card>
        )}

        {/* Account Type Distribution */}
        {accountTypeData.some((d: any) => d.y > 0) && (
          <Card style={globalStyles.card}>
            <Card.Content>
              <Text style={globalStyles.sectionTitle}>Account Types</Text>
              <View style={[globalStyles.row, { marginVertical: 12 }]}>
                {accountTypeData.map((item: any) => (
                  <View key={item.x} style={{ flex: 1, alignItems: 'center' }}>
                    <Text style={[globalStyles.currencyText, { fontSize: 24 }]}>{item.y}</Text>
                    <Text style={globalStyles.smallText}>{item.x}</Text>
                  </View>
                ))}
              </View>
            </Card.Content>
          </Card>
        )}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Snackbar */}
      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={2000}
      >
        {snackbarMessage}
      </Snackbar>
    </View>
  );
};

const styles = StyleSheet.create({
  scrollView: {
    flex: 1,
    padding: 4,
  },
});

export default AnalyticsScreen;

