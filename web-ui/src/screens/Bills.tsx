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
  FAB,
  Dialog,
  Portal,
  TextInput,
  Button,
  SegmentedButtons,
  Snackbar,
  Chip,
} from 'react-native-paper';
import { useQuery, useMutation } from '@apollo/client';
import { GET_ALL_BILLS, CREATE_BILL } from '../graphql/queries';
import { globalStyles } from '../theme';
import { formatCurrency, formatDate, getDayLabel, getFrequencyLabel } from '../utils/formatters';
import { VictoryPie, VictoryChart } from 'victory-native';

const { width } = Dimensions.get('window');

interface BillsScreenProps {
  navigation: any;
}

const BillsScreen: React.FC<BillsScreenProps> = ({ navigation }) => {
  const theme = useTheme();
  const [dialogVisible, setDialogVisible] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [filterFrequency, setFilterFrequency] = useState<string | null>(null);

  // Form states
  const [billName, setBillName] = useState('');
  const [amount, setAmount] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [frequency, setFrequency] = useState<string>('monthly');

  const { data: billsData, loading: billsLoading, refetch: refetchBills } = useQuery(GET_ALL_BILLS);

  const [createBill] = useMutation(CREATE_BILL, {
    onCompleted: (data) => {
      if (data.createBill.success) {
        setSnackbarMessage('Bill created successfully');
        setSnackbarVisible(true);
        resetForm();
        setDialogVisible(false);
        refetchBills();
      } else {
        setSnackbarMessage(data.createBill.message);
        setSnackbarVisible(true);
      }
    },
    onError: (error) => {
      setSnackbarMessage('Failed to create bill');
      setSnackbarVisible(true);
    },
  });

  const resetForm = () => {
    setBillName('');
    setAmount('');
    setDueDate('');
    setFrequency('monthly');
  };

  const handleCreateBill = () => {
    if (!billName || !amount || !dueDate) {
      setSnackbarMessage('Please fill in all required fields');
      setSnackbarVisible(true);
      return;
    }

    createBill({
      variables: {
        billName,
        amount: parseFloat(amount),
        dueDate: parseInt(dueDate),
        frequency,
      },
    });
  };

  let bills = billsData?.allBills || [];
  if (filterFrequency) {
    bills = bills.filter((bill: any) => bill.frequency === filterFrequency);
  }

  // Calculate statistics
  const totalMonthlyBills = billsData?.allBills
    ?.filter((bill: any) => bill.frequency === 'monthly')
    .reduce((sum: number, bill: any) => sum + bill.amount, 0) || 0;

  const billsByFrequency = (billsData?.allBills || []).reduce((acc: any, bill: any) => {
    acc[bill.frequency] = (acc[bill.frequency] || 0) + 1;
    return acc;
  }, {});

  const chartData = Object.entries(billsByFrequency).map(([key, value]: any) => ({
    x: key,
    y: value,
  }));

  if (billsLoading) {
    return (
      <View style={[globalStyles.centerContainer, { backgroundColor: theme.colors.background }]}>
        <Text>Loading bills...</Text>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
      <Appbar.Header>
        <Appbar.Content title="Bills" subtitle={`${bills.length} bills`} />
        <Appbar.Action icon="refresh" onPress={() => refetchBills()} />
      </Appbar.Header>

      <ScrollView style={styles.scrollView}>
        {/* Statistics Card */}
        <Card style={globalStyles.card}>
          <Card.Content>
            <Text style={globalStyles.sectionTitle}>Monthly Bills</Text>
            <Text style={[globalStyles.currencyNegative, { fontSize: 28, marginBottom: 12 }]}>
              -{formatCurrency(totalMonthlyBills)}
            </Text>
            <Text style={globalStyles.smallText}>
              {billsData?.allBills?.filter((b: any) => b.frequency === 'monthly').length || 0} recurring bills
            </Text>
          </Card.Content>
        </Card>

        {/* Frequency Filter */}
        {Object.keys(billsByFrequency).length > 0 && (
          <View style={{ paddingHorizontal: 12, marginVertical: 12 }}>
            <View style={globalStyles.row}>
              <Chip
                selected={filterFrequency === null}
                onPress={() => setFilterFrequency(null)}
                style={{ marginRight: 8 }}
              >
                All ({bills.length})
              </Chip>
              {Object.keys(billsByFrequency).map((freq: any) => (
                <Chip
                  key={freq}
                  selected={filterFrequency === freq}
                  onPress={() => setFilterFrequency(freq)}
                  style={{ marginRight: 8 }}
                >
                  {getFrequencyLabel(freq)} ({billsByFrequency[freq]})
                </Chip>
              ))}
            </View>
          </View>
        )}

        {/* Bills List */}
        {bills.length > 0 ? (
          bills.map((bill: any, index: number) => {
            const billDate = new Date(bill.nextDueDate);
            const today = new Date();
            const daysUntil = Math.ceil((billDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
            const isOverdue = daysUntil < 0;
            const isDueSoon = daysUntil <= 7 && daysUntil > 0;

            return (
              <Card
                key={`${bill.id}-${index}`}
                style={[
                  globalStyles.card,
                  isOverdue && { borderLeftWidth: 4, borderLeftColor: '#D32F2F' },
                  isDueSoon && { borderLeftWidth: 4, borderLeftColor: '#F57C00' },
                ]}
              >
                <Card.Content>
                  <View style={globalStyles.row}>
                    <View style={{ flex: 1 }}>
                      <Text style={globalStyles.textBold}>{bill.billName}</Text>
                      <Text style={[globalStyles.smallText, { marginTop: 4 }]}>
                        {getFrequencyLabel(bill.frequency)} • Due {getDayLabel(bill.dueDate)}
                      </Text>
                    </View>
                    <Text style={globalStyles.currencyNegative}>{formatCurrency(bill.amount)}</Text>
                  </View>
                  <View style={[globalStyles.row, { marginTop: 12 }]}>
                    <Text
                      style={[
                        globalStyles.smallText,
                        {
                          color: isOverdue ? '#D32F2F' : isDueSoon ? '#F57C00' : '#4CAF50',
                          fontWeight: '600',
                        },
                      ]}
                    >
                      {isOverdue
                        ? `${Math.abs(daysUntil)} days overdue`
                        : isDueSoon
                        ? `${daysUntil} days until due`
                        : `Next: ${formatDate(billDate)}`}
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
                No bills found. Create a bill to get started.
              </Text>
            </Card.Content>
          </Card>
        )}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Create Bill Dialog */}
      <Portal>
        <Dialog visible={dialogVisible} onDismiss={() => setDialogVisible(false)}>
          <Dialog.Title>Create Bill</Dialog.Title>
          <Dialog.Content>
            <TextInput
              label="Bill Name"
              value={billName}
              onChangeText={setBillName}
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
              label="Due Date (1-31)"
              value={dueDate}
              onChangeText={setDueDate}
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
            <Button onPress={handleCreateBill}>Create</Button>
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

export default BillsScreen;

