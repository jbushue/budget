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
  Switch,
  Divider,
  Button,
  Dialog,
  Portal,
  Snackbar,
} from 'react-native-paper';
import { useMutation } from '@apollo/client';
import { SAVE_DATABASE, LOAD_DATABASE } from '../graphql/queries';
import { globalStyles } from '../theme';

interface SettingsScreenProps {
  navigation: any;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
}

const SettingsScreen: React.FC<SettingsScreenProps> = ({
  navigation,
  isDarkMode,
  onToggleDarkMode,
}) => {
  const theme = useTheme();
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [dialogVisible, setDialogVisible] = useState(false);
  const [dialogTitle, setDialogTitle] = useState('');
  const [dialogMessage, setDialogMessage] = useState('');

  const [saveDatabase] = useMutation(SAVE_DATABASE, {
    onCompleted: (data) => {
      setSnackbarMessage(data.saveDatabase.message);
      setSnackbarVisible(true);
    },
    onError: () => {
      setSnackbarMessage('Failed to save data');
      setSnackbarVisible(true);
    },
  });

  const [loadDatabase] = useMutation(LOAD_DATABASE, {
    onCompleted: (data) => {
      setSnackbarMessage(data.loadDatabase.message);
      setSnackbarVisible(true);
    },
    onError: () => {
      setSnackbarMessage('Failed to load data');
      setSnackbarVisible(true);
    },
  });

  const handleSaveDatabase = () => {
    setDialogTitle('Save to Database?');
    setDialogMessage('This will save all your current financial data to the database.');
    setDialogVisible(true);
  };

  const handleLoadDatabase = () => {
    setDialogTitle('Load from Database?');
    setDialogMessage('This will load your saved financial data from the database.');
    setDialogVisible(true);
  };

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.background }}>
      <Appbar.Header>
        <Appbar.Content title="Settings" />
      </Appbar.Header>

      <ScrollView style={styles.scrollView}>
        {/* Appearance Section */}
        <Text style={[globalStyles.sectionTitle, globalStyles.paddingHorizontal16]}>
          Appearance
        </Text>
        <Card style={globalStyles.card}>
          <Card.Content>
            <View style={globalStyles.row}>
              <View>
                <Text style={globalStyles.textBold}>Dark Mode</Text>
                <Text style={[globalStyles.smallText, { marginTop: 4 }]}>
                  {isDarkMode ? 'Enabled' : 'Disabled'}
                </Text>
              </View>
              <Switch value={isDarkMode} onValueChange={onToggleDarkMode} />
            </View>
          </Card.Content>
        </Card>

        <Text style={[globalStyles.sectionTitle, globalStyles.paddingHorizontal16]}>
          Data Management
        </Text>

        {/* Save Database */}
        <Card style={globalStyles.card}>
          <Card.Content>
            <View style={globalStyles.row}>
              <View style={{ flex: 1 }}>
                <Text style={globalStyles.textBold}>Save to Database</Text>
                <Text style={[globalStyles.smallText, { marginTop: 4 }]}>
                  Save all financial data to local database
                </Text>
              </View>
            </View>
            <Button
              mode="contained-tonal"
              onPress={handleSaveDatabase}
              style={{ marginTop: 12 }}
            >
              Save
            </Button>
          </Card.Content>
        </Card>

        {/* Load Database */}
        <Card style={globalStyles.card}>
          <Card.Content>
            <View style={globalStyles.row}>
              <View style={{ flex: 1 }}>
                <Text style={globalStyles.textBold}>Load from Database</Text>
                <Text style={[globalStyles.smallText, { marginTop: 4 }]}>
                  Restore previously saved financial data
                </Text>
              </View>
            </View>
            <Button
              mode="contained-tonal"
              onPress={handleLoadDatabase}
              style={{ marginTop: 12 }}
            >
              Load
            </Button>
          </Card.Content>
        </Card>

        {/* About Section */}
        <Text style={[globalStyles.sectionTitle, globalStyles.paddingHorizontal16]}>
          About
        </Text>
        <Card style={globalStyles.card}>
          <Card.Content>
            <View>
              <View style={[globalStyles.row, { marginVertical: 8 }]}>
                <Text style={globalStyles.textBold}>Application</Text>
                <Text style={globalStyles.smallText}>Budget Manager</Text>
              </View>
              <Divider style={{ marginVertical: 8 }} />
              <View style={[globalStyles.row, { marginVertical: 8 }]}>
                <Text style={globalStyles.textBold}>Version</Text>
                <Text style={globalStyles.smallText}>1.0.0</Text>
              </View>
              <Divider style={{ marginVertical: 8 }} />
              <View style={[globalStyles.row, { marginVertical: 8 }]}>
                <Text style={globalStyles.textBold}>API Server</Text>
                <Text style={globalStyles.smallText}>GraphQL API</Text>
              </View>
            </View>
          </Card.Content>
        </Card>

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Confirmation Dialog */}
      <Portal>
        <Dialog visible={dialogVisible} onDismiss={() => setDialogVisible(false)}>
          <Dialog.Title>{dialogTitle}</Dialog.Title>
          <Dialog.Content>
            <Text>{dialogMessage}</Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setDialogVisible(false)}>Cancel</Button>
            <Button
              onPress={() => {
                if (dialogTitle.includes('Save')) {
                  saveDatabase();
                } else {
                  loadDatabase();
                }
                setDialogVisible(false);
              }}
            >
              Confirm
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

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

export default SettingsScreen;

