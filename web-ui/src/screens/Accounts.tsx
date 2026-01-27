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
} from 'react-native-paper';
import { useQuery, useMutation } from '@apollo/client';
import { GET_ALL_BANKS, CREATE_ACCOUNT, UPDATE_BALANCE } from '../graphql/queries';
import { globalStyles } from '../theme';
import { formatCurrency } from '../utils/formatters';

const { width } = Dimensions.get('window');

interface AccountsScreenProps {
  navigation: any;
}

const AccountsScreen: React.FC<AccountsScreenProps> = ({ navigation }) => {
  const theme = useTheme();
  const [dialogVisible, setDialogVisible] = useState(false);
  const [updateDialogVisible, setUpdateDialogVisible] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  // Form states
  const [selectedBank, setSelectedBank] = useState('');
  const [accountName, setAccountName] = useState('');
  const [accountType, setAccountType] = useState<'checking' | 'savings' | 'credit'>('checking');
  const [balance, setBalance] = useState('');
  const [interestRate, setInterestRate] = useState('');
  const [creditLimit, setCreditLimit] = useState('');

  // Update balance states
  const [selectedUpdateBank, setSelectedUpdateBank] = useState('');
  const [selectedUpdateAccount, setSelectedUpdateAccount] = useState('');
  const [newBalance, setNewBalance] = useState('');

  const { data: banksData, loading: banksLoading, refetch: refetchBanks } = useQuery(GET_ALL_BANKS);
  const [createAccount] = useMutation(CREATE_ACCOUNT, {
    onCompleted: (data) => {
      if (data.createAccount.success) {
        setSnackbarMessage('Account created successfully');
        setSnackbarVisible(true);
        resetForm();
        setDialogVisible(false);
        refetchBanks();
      } else {
        setSnackbarMessage(data.createAccount.message);
        setSnackbarVisible(true);
      }
    },
    onError: (error) => {
      setSnackbarMessage('Failed to create account');
      setSnackbarVisible(true);
    },
  });

  const [updateBalance] = useMutation(UPDATE_BALANCE, {
    onCompleted: (data) => {
      if (data.updateAccountBalance.success) {
        setSnackbarMessage('Balance updated successfully');
        setSnackbarVisible(true);
        setUpdateDialogVisible(false);
        refetchBanks();
      } else {
        setSnackbarMessage(data.updateAccountBalance.message);
        setSnackbarVisible(true);
      }
    },
  });

  const resetForm = () => {
    setSelectedBank('');
    setAccountName('');
    setAccountType('checking');
    setBalance('');
    setInterestRate('');
    setCreditLimit('');
  };

  const handleCreateAccount = () => {
    if (!selectedBank || !accountName) {
      setSnackbarMessage('Please fill in all required fields');
      setSnackbarVisible(true);
      return;
    }

    createAccount({
      variables: {
        bankName: selectedBank,
        accountName,
        accountType,
        balance: balance ? parseFloat(balance) : 0,
        interestRate: interestRate ? parseFloat(interestRate) : 0,
        creditLimit: creditLimit ? parseFloat(creditLimit) : undefined,
      },
    });
  };

  const handleUpdateBalance = () => {
    if (!selectedUpdateBank || !selectedUpdateAccount || !newBalance) {
      setSnackbarMessage('Please fill in all fields');
      setSnackbarVisible(true);
      return;
    }

    updateBalance({
      variables: {
        bankName: selectedUpdateBank,
        accountName: selectedUpdateAccount,
        newBalance: parseFloat(newBalance),
      },
    });
  };

  const banks = banksData?.allBanks || [];

  if (banksLoading) {
    return (
      <View style={[globalStyles.centerContainer, { backgroundColor: theme.colors.background }]}>
        <Text>Loading accounts...</Text>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
      <Appbar.Header>
        <Appbar.Content title="Accounts" />
        <Appbar.Action icon="refresh" onPress={() => refetchBanks()} />
      </Appbar.Header>

      <ScrollView style={styles.scrollView}>
        {banks.map((bank: any) => (
          <View key={bank.name}>
            {/* Bank Header */}
            <Card style={[globalStyles.card, { backgroundColor: theme.colors.primary }]}>
              <Card.Content>
                <Text style={[globalStyles.textBold, { color: '#FFF', fontSize: 16 }]}>
                  {bank.name}
                </Text>
                <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12, marginTop: 4 }}>
                  {bank.bankType}
                </Text>
                <Text style={{ color: '#FFF', fontSize: 20, fontWeight: '700', marginTop: 12 }}>
                  {formatCurrency(bank.totalBalance)}
                </Text>
              </Card.Content>
            </Card>

            {/* Bank Accounts */}
            {bank.bankAccounts?.length > 0 && (
              <View style={{ marginHorizontal: 12, marginTop: 8 }}>
                {bank.bankAccounts.map((account: any) => (
                  <Card
                    key={account.id}
                    style={[globalStyles.card, { marginBottom: 8 }]}
                    onPress={() => {
                      setSelectedUpdateBank(bank.name);
                      setSelectedUpdateAccount(account.accountName);
                      setUpdateDialogVisible(true);
                    }}
                  >
                    <Card.Content>
                      <View style={globalStyles.row}>
                        <View>
                          <Text style={globalStyles.textBold}>{account.accountName}</Text>
                          <Text style={[globalStyles.smallText, { marginTop: 4 }]}>
                            {account.accountType} • APR {account.interestRate}%
                          </Text>
                        </View>
                        <Text style={globalStyles.currencyText}>{formatCurrency(account.balance)}</Text>
                      </View>
                    </Card.Content>
                  </Card>
                ))}
              </View>
            )}

            {/* Credit Accounts */}
            {bank.creditAccounts?.length > 0 && (
              <View style={{ marginHorizontal: 12, marginTop: 8 }}>
                {bank.creditAccounts.map((account: any) => (
                  <Card
                    key={account.id}
                    style={[globalStyles.card, { marginBottom: 8 }]}
                    onPress={() => {
                      setSelectedUpdateBank(bank.name);
                      setSelectedUpdateAccount(account.accountName);
                      setUpdateDialogVisible(true);
                    }}
                  >
                    <Card.Content>
                      <View style={globalStyles.row}>
                        <View style={{ flex: 1 }}>
                          <Text style={globalStyles.textBold}>{account.accountName}</Text>
                          <Text style={[globalStyles.smallText, { marginTop: 4 }]}>
                            Credit Card • {account.accountType}
                          </Text>
                        </View>
                        <View style={{ alignItems: 'flex-end' }}>
                          <Text style={globalStyles.currencyNegative}>
                            {formatCurrency(account.balance)}
                          </Text>
                          <Text style={[globalStyles.smallText, { marginTop: 4 }]}>
                            of {formatCurrency(account.creditLimit)}
                          </Text>
                        </View>
                      </View>
                      <View style={[globalStyles.row, { marginTop: 12 }]}>
                        <Text style={globalStyles.smallText}>
                          Available: {formatCurrency(account.availableCredit)}
                        </Text>
                      </View>
                    </Card.Content>
                  </Card>
                ))}
              </View>
            )}

            <View style={{ height: 20 }} />
          </View>
        ))}

        {banks.length === 0 && (
          <Card style={[globalStyles.card, { marginTop: 32 }]}>
            <Card.Content>
              <Text style={[globalStyles.text, { textAlign: 'center' }]}>
                No banks found. Create a bank first.
              </Text>
            </Card.Content>
          </Card>
        )}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Create Account Dialog */}
      <Portal>
        <Dialog visible={dialogVisible} onDismiss={() => setDialogVisible(false)}>
          <Dialog.Title>Create Account</Dialog.Title>
          <Dialog.Content>
            {/* Bank Selection */}
            <Text style={[globalStyles.textBold, { marginBottom: 8 }]}>Select Bank</Text>
            <SegmentedButtons
              value={selectedBank}
              onValueChange={setSelectedBank}
              buttons={banks.map((bank: any) => ({
                value: bank.name,
                label: bank.name,
              }))}
              style={{ marginBottom: 16 }}
            />

            {/* Account Name */}
            <TextInput
              label="Account Name"
              value={accountName}
              onChangeText={setAccountName}
              mode="outlined"
              style={{ marginBottom: 12 }}
            />

            {/* Account Type */}
            <Text style={[globalStyles.textBold, { marginBottom: 8 }]}>Account Type</Text>
            <SegmentedButtons
              value={accountType}
              onValueChange={(value) => setAccountType(value as any)}
              buttons={[
                { value: 'checking', label: 'Checking' },
                { value: 'savings', label: 'Savings' },
                { value: 'credit', label: 'Credit' },
              ]}
              style={{ marginBottom: 16 }}
            />

            {/* Balance */}
            <TextInput
              label="Initial Balance"
              value={balance}
              onChangeText={setBalance}
              mode="outlined"
              keyboardType="decimal-pad"
              style={{ marginBottom: 12 }}
            />

            {/* Interest Rate */}
            <TextInput
              label="Interest Rate (%)"
              value={interestRate}
              onChangeText={setInterestRate}
              mode="outlined"
              keyboardType="decimal-pad"
              style={{ marginBottom: 12 }}
            />

            {/* Credit Limit (for credit cards) */}
            {accountType === 'credit' && (
              <TextInput
                label="Credit Limit"
                value={creditLimit}
                onChangeText={setCreditLimit}
                mode="outlined"
                keyboardType="decimal-pad"
                style={{ marginBottom: 12 }}
              />
            )}
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setDialogVisible(false)}>Cancel</Button>
            <Button onPress={handleCreateAccount}>Create</Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* Update Balance Dialog */}
      <Portal>
        <Dialog visible={updateDialogVisible} onDismiss={() => setUpdateDialogVisible(false)}>
          <Dialog.Title>Update Balance</Dialog.Title>
          <Dialog.Content>
            <Text style={[globalStyles.text, { marginBottom: 12 }]}>
              {selectedUpdateBank} • {selectedUpdateAccount}
            </Text>
            <TextInput
              label="New Balance"
              value={newBalance}
              onChangeText={setNewBalance}
              mode="outlined"
              keyboardType="decimal-pad"
            />
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setUpdateDialogVisible(false)}>Cancel</Button>
            <Button onPress={handleUpdateBalance}>Update</Button>
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

export default AccountsScreen;

