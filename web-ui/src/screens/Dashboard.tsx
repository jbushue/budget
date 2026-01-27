import React, { useEffect, useState } from 'react';
import {
  ScrollView,
  StyleSheet,
  View,
  RefreshControl,
  Dimensions,
  Platform,
} from 'react-native';
import {
  Card,
  Text,
  useTheme,
  Appbar,
  FAB,
  ProgressBar,
  Snackbar,
} from 'react-native-paper';
import { useQuery } from '@apollo/client';
import { VictoryBar, VictoryLine, VictoryChart, VictoryAxis } from 'victory-native';
import { GET_SNAPSHOT, GET_PROJECTION } from '../graphql/queries';
import { globalStyles } from '../theme';
import { formatCurrency, formatDate } from '../utils/formatters';

const { width } = Dimensions.get('window');

interface DashboardProps {
  navigation: any;
}

const Dashboard: React.FC<DashboardProps> = ({ navigation }) => {
  const theme = useTheme();
  const [refreshing, setRefreshing] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  const { data: snapshotData, loading: snapshotLoading, refetch: refetchSnapshot } = useQuery(GET_SNAPSHOT);
  const { data: projectionData, refetch: refetchProjection } = useQuery(GET_PROJECTION, {
    variables: { days: 90 },
  });

  useEffect(() => {
    refetchSnapshot();
    refetchProjection();
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refetchSnapshot();
      await refetchProjection();
      setSnackbarMessage('Data refreshed successfully');
      setSnackbarVisible(true);
    } catch (error) {
      setSnackbarMessage('Failed to refresh data');
      setSnackbarVisible(true);
    } finally {
      setRefreshing(false);
    }
  };

  const snapshot = snapshotData?.snapshot;
  const projection = projectionData?.projection;

  // Prepare chart data
  const projectionChartData = projection?.snapshots?.slice(0, 30).map((snap: any) => ({
    x: new Date(snap.date).getDate(),
    y: snap.total,
  })) || [];

  const bankChartData = snapshot?.banks?.map((bank: any, idx: number) => ({
    x: bank.name,
    y: bank.totalBalance,
  })) || [];

  if (snapshotLoading) {
    return (
      <View style={[globalStyles.centerContainer, { backgroundColor: theme.colors.background }]}>
        <Text>Loading financial data...</Text>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
      <Appbar.Header>
        <Appbar.Content title="Financial Dashboard" subtitle={snapshot?.timestamp ? formatDate(new Date(snapshot.timestamp)) : ''} />
        <Appbar.Action icon="refresh" onPress={handleRefresh} />
      </Appbar.Header>

      <ScrollView
        style={styles.scrollView}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        {/* Net Worth Summary */}
        <Card style={[globalStyles.card, { backgroundColor: theme.colors.primary }]}>
          <Card.Content>
            <Text style={styles.summaryLabel}>Net Worth</Text>
            <Text style={[styles.summaryValue, { color: '#FFF' }]}>
              {formatCurrency(snapshot?.netWorth || 0)}
            </Text>
            <View style={[globalStyles.row, { marginTop: 16 }]}>
              <View>
                <Text style={styles.smallSummary}>Assets</Text>
                <Text style={[styles.summarySubtext, { color: '#FFF' }]}>
                  {formatCurrency(snapshot?.totalAssets || 0)}
                </Text>
              </View>
              <View>
                <Text style={styles.smallSummary}>Liabilities</Text>
                <Text style={[styles.summarySubtext, { color: '#FFF' }]}>
                  {formatCurrency(snapshot?.totalLiabilities || 0)}
                </Text>
              </View>
            </View>
          </Card.Content>
        </Card>

        {/* Quick Stats */}
        <View style={styles.quickStatsContainer}>
          <Card style={[globalStyles.card, { flex: 1, marginRight: 6 }]}>
            <Card.Content>
              <Text style={styles.statLabel}>Upcoming Bills</Text>
              <Text style={styles.statValue}>{snapshot?.upcomingBills30Days?.length || 0}</Text>
              <Text style={styles.statSubtext}>Next 30 days</Text>
            </Card.Content>
          </Card>
          <Card style={[globalStyles.card, { flex: 1, marginLeft: 6 }]}>
            <Card.Content>
              <Text style={styles.statLabel}>Income Sources</Text>
              <Text style={styles.statValue}>{snapshot?.upcomingIncome30Days?.length || 0}</Text>
              <Text style={styles.statSubtext}>Scheduled</Text>
            </Card.Content>
          </Card>
        </View>

        {/* Banks Overview */}
        <View style={globalStyles.paddingHorizontal16}>
          <Text style={globalStyles.sectionTitle}>Banks</Text>
        </View>
        {snapshot?.banks?.map((bank: any) => (
          <Card key={bank.name} style={globalStyles.card}>
            <Card.Content>
              <View style={globalStyles.row}>
                <View>
                  <Text style={globalStyles.textBold}>{bank.name}</Text>
                  <Text style={globalStyles.smallText}>{bank.bankType}</Text>
                </View>
                <Text style={globalStyles.currencyText}>{formatCurrency(bank.totalBalance)}</Text>
              </View>

              {/* Bank Accounts */}
              {bank.bankAccounts?.length > 0 && (
                <View style={{ marginTop: 12 }}>
                  {bank.bankAccounts.map((account: any) => (
                    <View key={account.id} style={[globalStyles.row, { marginVertical: 8 }]}>
                      <View>
                        <Text style={styles.accountName}>{account.accountName}</Text>
                        <Text style={styles.accountType}>{account.accountType}</Text>
                      </View>
                      <Text style={styles.accountBalance}>{formatCurrency(account.balance)}</Text>
                    </View>
                  ))}
                </View>
              )}

              {/* Credit Accounts */}
              {bank.creditAccounts?.length > 0 && (
                <View style={{ marginTop: 12, borderTopWidth: 1, borderTopColor: '#E0E0E0', paddingTop: 12 }}>
                  {bank.creditAccounts.map((account: any) => (
                    <View key={account.id} style={{ marginVertical: 8 }}>
                      <View style={globalStyles.row}>
                        <Text style={styles.accountName}>{account.accountName}</Text>
                        <Text style={styles.creditLimit}>{formatCurrency(account.creditLimit)}</Text>
                      </View>
                      <ProgressBar
                        progress={account.balance / account.creditLimit}
                        style={{ marginVertical: 4, height: 4 }}
                        color={account.balance / account.creditLimit > 0.8 ? '#D32F2F' : '#4CAF50'}
                      />
                      <View style={[globalStyles.row, { marginTop: 4 }]}>
                        <Text style={styles.smallText}>Owed: {formatCurrency(account.balance)}</Text>
                        <Text style={styles.smallText}>Available: {formatCurrency(account.availableCredit)}</Text>
                      </View>
                    </View>
                  ))}
                </View>
              )}
            </Card.Content>
          </Card>
        ))}

        {/* Charts Section */}
        <View style={globalStyles.paddingHorizontal16}>
          <Text style={globalStyles.sectionTitle}>90-Day Projection</Text>
        </View>
        {projectionChartData.length > 0 && (
          <Card style={globalStyles.card}>
            <Card.Content>
              <VictoryChart width={width - 40} height={250}>
                <VictoryAxis
                  dependentAxis
                  tickFormat={(t: number) => `$${(t / 1000).toFixed(0)}k`}
                />
                <VictoryAxis />
                <VictoryLine
                  data={projectionChartData}
                  style={{
                    data: { stroke: theme.colors.primary, strokeWidth: 2 },
                  }}
                />
              </VictoryChart>
              <View style={[globalStyles.row, { marginTop: 12 }]}>
                <View>
                  <Text style={styles.projectionLabel}>Total Income</Text>
                  <Text style={[globalStyles.currencyText, { color: theme.colors.success }]}>
                    +{formatCurrency(projection?.totalIncome || 0)}
                  </Text>
                </View>
                <View>
                  <Text style={styles.projectionLabel}>Total Expenses</Text>
                  <Text style={[globalStyles.currencyNegative]}>
                    -{formatCurrency(projection?.totalExpenses || 0)}
                  </Text>
                </View>
              </View>
            </Card.Content>
          </Card>
        )}

        {/* Upcoming Bills */}
        <View style={globalStyles.paddingHorizontal16}>
          <Text style={globalStyles.sectionTitle}>Upcoming Bills</Text>
        </View>
        {snapshot?.upcomingBills30Days?.length ? (
          snapshot.upcomingBills30Days.map((bill: any) => (
            <Card key={bill.id} style={globalStyles.card}>
              <Card.Content>
                <View style={globalStyles.row}>
                  <View>
                    <Text style={globalStyles.textBold}>{bill.billName}</Text>
                    <Text style={globalStyles.smallText}>{bill.frequency}</Text>
                  </View>
                  <Text style={globalStyles.currencyNegative}>{formatCurrency(bill.amount)}</Text>
                </View>
                <Text style={[styles.dueDate, { marginTop: 8 }]}>
                  Due: {formatDate(new Date(bill.nextDueDate))}
                </Text>
              </Card.Content>
            </Card>
          ))
        ) : (
          <Card style={globalStyles.card}>
            <Card.Content>
              <Text style={globalStyles.smallText}>No upcoming bills</Text>
            </Card.Content>
          </Card>
        )}

        {/* Upcoming Income */}
        <View style={globalStyles.paddingHorizontal16}>
          <Text style={globalStyles.sectionTitle}>Income</Text>
        </View>
        {snapshot?.upcomingIncome30Days?.length ? (
          snapshot.upcomingIncome30Days.map((income: any) => (
            <Card key={income.id} style={globalStyles.card}>
              <Card.Content>
                <View style={globalStyles.row}>
                  <View>
                    <Text style={globalStyles.textBold}>{income.sourceName}</Text>
                    <Text style={globalStyles.smallText}>{income.frequency}</Text>
                  </View>
                  <Text style={[globalStyles.currencyText, { color: theme.colors.success }]}>
                    +{formatCurrency(income.amount)}
                  </Text>
                </View>
                <Text style={[styles.dueDate, { marginTop: 8 }]}>
                  Next: {formatDate(new Date(income.nextPayDate))}
                </Text>
              </Card.Content>
            </Card>
          ))
        ) : (
          <Card style={globalStyles.card}>
            <Card.Content>
              <Text style={globalStyles.smallText}>No income sources configured</Text>
            </Card.Content>
          </Card>
        )}

        <View style={{ height: 80 }} />
      </ScrollView>

      {/* FAB Button */}
      <FAB
        icon="plus"
        onPress={() => navigation.navigate('AddData')}
        style={[
          styles.fab,
          {
            backgroundColor: theme.colors.primary,
          },
        ]}
      />

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
    padding: 8,
  },
  summaryLabel: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.7)',
    marginBottom: 8,
  },
  summaryValue: {
    fontSize: 32,
    fontWeight: '700',
    marginBottom: 8,
  },
  summarySubtext: {
    fontSize: 12,
    marginTop: 4,
  },
  smallSummary: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.7)',
    marginBottom: 4,
  },
  quickStatsContainer: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    marginVertical: 8,
  },
  statLabel: {
    fontSize: 12,
    color: '#757575',
    marginBottom: 4,
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    color: '#2E7D32',
    marginBottom: 4,
  },
  statSubtext: {
    fontSize: 11,
    color: '#9E9E9E',
  },
  accountName: {
    fontSize: 13,
    fontWeight: '600',
    color: '#212121',
  },
  accountType: {
    fontSize: 11,
    color: '#757575',
    marginTop: 2,
  },
  accountBalance: {
    fontSize: 14,
    fontWeight: '700',
    color: '#2E7D32',
  },
  creditLimit: {
    fontSize: 12,
    fontWeight: '600',
    color: '#757575',
  },
  dueDate: {
    fontSize: 12,
    color: '#F57C00',
    fontWeight: '500',
  },
  projectionLabel: {
    fontSize: 12,
    color: '#757575',
    marginBottom: 4,
  },
  fab: {
    position: 'absolute',
    margin: 16,
    right: 0,
    bottom: 0,
  },
});

export default Dashboard;

