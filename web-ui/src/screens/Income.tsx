import React, { useState } from 'react';
import {
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import {
  Card,
  Text,
  useTheme,
  Appbar,
  FAB,
  Dialog,
  Portal,
  TextInput,
  Button,
  SegmentedButtons,
  Snackbar,
} from 'react-native-paper';
import { useQuery, useMutation } from '@apollo/client';
import { GET_ALL_INCOME, CREATE_INCOME } from '../graphql/queries';
import { globalStyles } from '../theme';
import { formatCurrency, formatDate, getDayLabel, getFrequencyLabel } from '../utils/formatters';

interface IncomeScreenProps {
  navigation: any;
}

const IncomeScreen: React.FC<IncomeScreenProps> = ({ navigation }) => {
  const theme = useTheme();
  const [dialogVisible, setDialogVisible] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  // Form states
  const [sourceName, setSourceName] = useState('');
  const [amount, setAmount] = useState('');
  const [frequency, setFrequency] = useState<string>('monthly');
  const [payDate, setPayDate] = useState('');

  const { data: incomeData, loading: incomeLoading, refetch: refetchIncome } = useQuery(GET_ALL_INCOME);

  const [createIncome] = useMutation(CREATE_INCOME, {
    onCompleted: (data) => {
      if (data.createIncomeSource.success) {
        setSnackbarMessage('Income source created successfully');
        setSnackbarVisible(true);
        resetForm();
        setDialogVisible(false);
        refetchIncome();
      } else {
        setSnackbarMessage(data.createIncomeSource.message);
        setSnackbarVisible(true);
      }
    },
    onError: (error) => {
      setSnackbarMessage('Failed to create income source');
      setSnackbarVisible(true);
    },
  });

  const resetForm = () => {
    setSourceName('');
    setAmount('');
    setFrequency('monthly');
    setPayDate('');
  };

  const handleCreateIncome = () => {
    if (!sourceName || !amount || !payDate) {
      setSnackbarMessage('Please fill in all required fields');
      setSnackbarVisible(true);
      return;
    }

    createIncome({
      variables: {
        sourceName,
        amount: parseFloat(amount),
        frequency,
        payDate: parseInt(payDate),
        distribution: {},
      },
    });
  };

  const incomes = incomeData?.allIncome || [];

  // Calculate statistics
  const totalMonthlyIncome = incomes
    .filter((income: any) => income.frequency === 'monthly')
    .reduce((sum: number, income: any) => sum + income.amount, 0) || 0;

  const annualIncome = incomes.reduce((sum: number, income: any) => {
    const freq = income.frequency;
    let multiplier = 1;
    if (freq === 'weekly') multiplier = 52;
    else if (freq === 'biweekly') multiplier = 26;
    else if (freq === 'monthly') multiplier = 12;
    else if (freq === 'quarterly') multiplier = 4;
    else if (freq === 'semi_annual') multiplier = 2;
    return sum + income.amount * multiplier;
  }, 0);

  if (incomeLoading) {
    return (
      <View style={[globalStyles.centerContainer, { backgroundColor: theme.colors.background }]}>
        <Text>Loading income sources...</Text>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
      <Appbar.Header>
        <Appbar.Content title="Income" subtitle={`${incomes.length} sources`} />
        <Appbar.Action icon="refresh" onPress={() => refetchIncome()} />
      </Appbar.Header>

      <ScrollView style={styles.scrollView}>
        {/* Statistics Cards */}
        <View style={{ flexDirection: 'row', paddingHorizontal: 12, marginVertical: 8, gap: 8 }}>
          <Card style={{ flex: 1, backgroundColor: theme.colors.primary }}>
            <Card.Content>
              <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12, marginBottom: 4 }}>
                Monthly
              </Text>
              <Text style={{ color: '#FFF', fontSize: 18, fontWeight: '700' }}>
                {formatCurrency(totalMonthlyIncome)}
              </Text>
            </Card.Content>
          </Card>
          <Card style={{ flex: 1, backgroundColor: theme.colors.secondary }}>
            <Card.Content>
              <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12, marginBottom: 4 }}>
                Annual
              </Text>
              <Text style={{ color: '#FFF', fontSize: 18, fontWeight: '700' }}>
                {formatCurrency(annualIncome)}
              </Text>
            </Card.Content>
          </Card>
        </View>

        {/* Income List */}
        {incomes.length > 0 ? (
          incomes.map((income: any) => {
            const incomeDate = new Date(income.nextPayDate);
            const today = new Date();
            const daysUntil = Math.ceil((incomeDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

            return (
              <Card key={income.id} style={globalStyles.card}>
                <Card.Content>
                  <View style={globalStyles.row}>
                    <View style={{ flex: 1 }}>
                      <Text style={globalStyles.textBold}>{income.sourceName}</Text>
                      <Text style={[globalStyles.smallText, { marginTop: 4 }]}>
                        {getFrequencyLabel(income.frequency)} • Pay on {getDayLabel(income.payDate)}
                      </Text>
                    </View>
                    <Text style={[globalStyles.currencyText, { color: theme.colors.success }]}>
                      +{formatCurrency(income.amount)}
                    </Text>
                  </View>
                  <View style={[globalStyles.row, { marginTop: 12 }]}>
                    <Text style={[globalStyles.smallText, { color: theme.colors.secondary, fontWeight: '600' }]}>
                      {daysUntil <= 0
                        ? 'Paid'
                        : daysUntil === 1
                        ? 'Tomorrow'
                        : `In ${daysUntil} days`}
                    </Text>
                    <Text style={globalStyles.smallText}>
                      Next: {formatDate(incomeDate)}
                    </Text>
                  </View>
                </Card.Content>
              </Card>
            );
          })
        ) : (
          <Card style={[globalStyles.card, { marginTop: 32 }]}>
            <Card.Content>
              <Text style={[globalStyles.text, { textAlign: 'center' }]}>
                No income sources. Add your first income to get started.
              </Text>
            </Card.Content>
          </Card>
        )}

        {/* Income Breakdown */}
        {incomes.length > 0 && (
          <View>
            <Text style={[globalStyles.sectionTitle, globalStyles.paddingHorizontal16]}>
              Annual Breakdown
            </Text>
            {incomes.map((income: any) => {
              const freq = income.frequency;
              let multiplier = 1;
              if (freq === 'weekly') multiplier = 52;
              else if (freq === 'biweekly') multiplier = 26;
              else if (freq === 'monthly') multiplier = 12;
              else if (freq === 'quarterly') multiplier = 4;
              else if (freq === 'semi_annual') multiplier = 2;
              const annual = income.amount * multiplier;

              return (
                <Card key={`annual-${income.id}`} style={globalStyles.card}>
                  <Card.Content>
                    <View style={globalStyles.row}>
                      <Text style={globalStyles.textBold}>{income.sourceName}</Text>
                      <Text style={[globalStyles.currencyText, { color: theme.colors.success }]}>
                        {formatCurrency(annual)}
                      </Text>
                    </View>
                  </Card.Content>
                </Card>
              );
            })}
          </View>
        )}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Create Income Dialog */}
      <Portal>
        <Dialog visible={dialogVisible} onDismiss={() => setDialogVisible(false)}>
          <Dialog.Title>Add Income Source</Dialog.Title>
          <Dialog.Content>
            <TextInput
              label="Source Name"
              value={sourceName}
              onChangeText={setSourceName}
              mode="outlined"
              style={{ marginBottom: 12 }}
            />

            <TextInput
              label="Amount"
              value={amount}
              onChangeText={setAmount}
              mode="outlined"
              keyboardType="decimal-pad"
              style={{ marginBottom: 12 }}
            />

            <TextInput
              label="Pay Date (1-31)"
              value={payDate}
              onChangeText={setPayDate}
              mode="outlined"
              keyboardType="number-pad"
              style={{ marginBottom: 12 }}
            />

            <Text style={[globalStyles.textBold, { marginBottom: 8 }]}>Frequency</Text>
            <SegmentedButtons
              value={frequency}
              onValueChange={setFrequency}
              buttons={[
                { value: 'weekly', label: 'Weekly' },
                { value: 'biweekly', label: 'Bi-weekly' },
                { value: 'monthly', label: 'Monthly' },
              ]}
              style={{ marginBottom: 12 }}
            />
            <SegmentedButtons
              value={frequency}
              onValueChange={setFrequency}
              buttons={[
                { value: 'quarterly', label: 'Quarterly' },
                { value: 'semi_annual', label: 'Semi-Annual' },
                { value: 'yearly', label: 'Yearly' },
              ]}
            />
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setDialogVisible(false)}>Cancel</Button>
            <Button onPress={handleCreateIncome}>Add</Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* FAB */}
      <FAB
        icon="plus"
        onPress={() => setDialogVisible(true)}
        style={[styles.fab, { backgroundColor: theme.colors.primary }]}
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
    padding: 4,
  },
  fab: {
    position: 'absolute',
    margin: 16,
    right: 0,
    bottom: 0,
  },
});

export default IncomeScreen;

