<template>
  <div>
    <div class="view-header">
      <div class="view-title">
        <h2>Settings</h2>
        <p class="view-sub">Preferences, alerts, sign-in, bank sync and backups.</p>
      </div>
    </div>

    <div class="tabs" role="tablist">
      <button v-for="t in TABS" :key="t.key" class="tab" :class="{ active: tab === t.key }" role="tab"
              :aria-selected="tab === t.key" @click="setTab(t.key)">
        <Icon :name="t.icon" :size="16" /> {{ t.label }}
      </button>
    </div>

    <template v-if="tab === 'general'">
      <AppearanceSettings />
      <PlanningSettings />
    </template>
    <AlertSettings v-else-if="tab === 'alerts'" />
    <SecuritySettings v-else-if="tab === 'account'" />
    <template v-else-if="tab === 'data'">
      <DataFiles />
      <BackgroundJobs v-if="authState.user?.is_admin" />
    </template>

    <!-- SimpleFIN Bridge -->
    <div v-if="tab === 'connections'" class="card">
      <div class="card-header"><span class="card-title">SimpleFIN bridge</span></div>
      <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem">
        Connect to <a href="https://bridge.simplefin.org/" target="_blank">SimpleFIN Bridge</a>
        to automatically sync account balances from your financial institutions.
      </p>

      <!-- Loading state -->
      <div v-if="sfinLoading && !sfinStatusResult" style="color:var(--text-muted);font-size:0.85rem">Loading SimpleFIN status...</div>

      <!-- Not connected -->
      <template v-else-if="!sfinStatus?.isConnected">
        <div style="display:flex;gap:0.5rem;align-items:flex-end">
          <div class="form-group" style="flex:1;margin-bottom:0">
            <label>Setup token</label>
            <input v-model="sfinSetupToken" placeholder="Paste setup token from SimpleFIN Bridge..." style="font-family:monospace;font-size:0.8rem" />
          </div>
          <button class="btn btn-primary" @click="connectSimplefin" :disabled="!sfinSetupToken.trim() || sfinConnecting">
            {{ sfinConnecting ? 'Connecting...' : 'Connect' }}
          </button>
        </div>
        <p style="font-size:0.8rem;color:var(--text-muted);margin-top:0.5rem">
          1. Go to <a href="https://bridge.simplefin.org/" target="_blank">bridge.simplefin.org</a> and create a connection<br>
          2. Copy the setup token and paste it above<br>
          3. Click Connect — the token is single-use
        </p>
      </template>

      <!-- Connected -->
      <template v-else>
        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem">
          <div style="width:10px;height:10px;borderRadius:50%;background:var(--success)"></div>
          <span style="font-weight:500">Connected</span>
          <span v-if="sfinStatus.lastSyncAt" style="color:var(--text-muted);font-size:0.8rem;margin-left:0.5rem">
            Last sync: {{ fmtDate(sfinStatus.lastSyncAt) }}
          </span>
          <span style="color:var(--text-muted);font-size:0.8rem;margin-left:0.5rem">
            · {{ sfinStatus.mappedAccountCount }} mapped account(s)
          </span>
        </div>

        <div style="display:flex;gap:0.5rem;margin-bottom:1rem">
          <button class="btn btn-success btn-sm" @click="syncBalances" :disabled="sfinSyncing">
            {{ sfinSyncing ? 'Syncing...' : 'Sync balances now' }}
          </button>
          <button class="btn btn-outline btn-sm" @click="fetchSfinAccounts" :disabled="sfinFetching">
            {{ sfinFetching ? 'Fetching...' : 'Refresh Accounts' }}
          </button>
          <button class="btn btn-danger btn-sm" @click="disconnectSimplefin">Disconnect</button>
        </div>
        <SimplefinAutoSync />

        <!-- Sync result -->
        <div v-if="sfinSyncMsg" style="margin-bottom:1rem;font-size:0.85rem;padding:0.5rem 0.75rem;border-radius:4px"
             :style="{ background: sfinSyncOk ? 'var(--success-bg, rgba(34,197,94,0.1))' : 'var(--danger-bg, rgba(239,68,68,0.1))', color: sfinSyncOk ? 'var(--success)' : 'var(--danger)' }">
          {{ sfinSyncMsg }}
        </div>
        <div v-if="sfinSyncDetails.length > 0" style="margin-bottom:1rem">
          <details>
            <summary style="font-size:0.8rem;color:var(--text-muted);cursor:pointer;margin-bottom:0.25rem">Sync details</summary>
            <div style="font-size:0.75rem;color:var(--text-muted);padding:0.5rem;background:var(--surface-alt);border-radius:4px">
              <div v-for="(d, i) in sfinSyncDetails" :key="i" style="margin-bottom:0.15rem">
                <span :style="{ color: d.status === 'updated' ? 'var(--success)' : 'var(--text-muted)' }">
                  {{ d.status === 'updated' ? '✓' : '–' }}
                </span>
                {{ d.account }}: {{ currency(d.previous) }} → {{ currency(d.new) }}
                <span v-if="d.status === 'unchanged'" style="opacity:0.6">(unchanged)</span>
              </div>
            </div>
          </details>
        </div>

        <!-- Account mapping table -->
        <div v-if="sfinAccounts.length > 0">
          <h4 style="margin-bottom:0.5rem">Account mapping</h4>
          <p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.75rem">
            Map each SimpleFIN account to a local bank account. Only mapped accounts will be synced.
          </p>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Institution</th>
                  <th>SimpleFIN account</th>
                  <th style="text-align:right">Balance</th>
                  <th>→ Local bank</th>
                  <th>→ Local account</th>
                  <th>Type</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="acc in sfinAccounts" :key="acc.id"
                    :style="acc.mappedBankName ? '' : 'opacity:0.7'">
                  <td style="font-size:0.85rem">{{ acc.orgName }}</td>
                  <td style="font-weight:500">
                    {{ acc.name }}
                    <span v-if="acc.mappedBankName" class="badge badge-success" style="margin-left:0.25rem">Mapped</span>
                  </td>
                  <td style="text-align:right;font-weight:600" :style="{ color: acc.balance >= 0 ? 'var(--success)' : 'var(--danger)' }">
                    {{ currency(acc.balance) }}
                  </td>
                  <td>
                    <select v-model="mappingForm[acc.id].bankName" style="font-size:0.8rem" @change="mappingForm[acc.id].accountName = ''">
                      <option value="">-- Select bank --</option>
                      <option v-for="b in banks" :key="b.name" :value="b.name">{{ b.name }}</option>
                    </select>
                  </td>
                  <td>
                    <select v-model="mappingForm[acc.id].accountName" style="font-size:0.8rem"
                            :disabled="!mappingForm[acc.id].bankName"
                            @change="onAccountSelected(acc.id)">
                      <option value="">-- Select account --</option>
                      <option v-for="la in allAccountsForBank(mappingForm[acc.id].bankName)" :key="la.fullName" :value="la.name">
                        {{ la.name }} ({{ la.type }})
                      </option>
                    </select>
                  </td>
                  <td>
                    <span style="font-size:0.8rem;color:var(--text-muted)">{{ mappingForm[acc.id].accountType }}</span>
                  </td>
                  <td style="white-space:nowrap">
                    <button
                      class="btn btn-primary btn-sm"
                      @click="saveMapping(acc)"
                      :disabled="!mappingForm[acc.id].bankName || !mappingForm[acc.id].accountName"
                      style="margin-right:0.25rem"
                    >Map</button>
                    <button
                      v-if="acc.mappedBankName"
                      class="btn btn-outline btn-sm"
                      @click="removeMapping(acc.id)"
                    >✕</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-else-if="!sfinFetching" style="color:var(--text-muted);font-size:0.85rem">
          No accounts fetched yet. Click "Refresh Accounts" to load accounts from SimpleFIN.
        </div>
      </template>

      <div v-if="sfinMessage" style="margin-top:0.75rem;font-size:0.85rem" :class="sfinMsgOk ? 'positive' : 'negative'">
        {{ sfinMessage }}
      </div>
    </div>

    <!-- Database management -->
    <div v-if="tab === 'data'" class="card">
      <div class="card-header"><span class="card-title">Database</span></div>
      <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1rem">
        Changes are saved automatically. Use these only if the data on the server was changed outside the app.
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:0.5rem">
        <button class="btn btn-outline" @click="loadDb" :disabled="loadingDb">
          {{ loadingDb ? 'Reloading...' : 'Reload from database' }}
        </button>
        <button class="btn btn-outline" @click="saveDb" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save everything now' }}
        </button>
      </div>
      <div v-if="dbMessage" style="margin-top:0.75rem;font-size:0.85rem" :class="dbSuccess ? 'positive' : 'negative'">
        {{ dbMessage }}
      </div>
      <DatabaseInfo />
    </div>

    <!-- Server status -->
    <div v-if="tab === 'data'" class="card">
      <div class="card-header">
        <span class="card-title">Server</span>
        <button class="btn btn-outline btn-sm" @click="checkHealth">Check status</button>
      </div>
      <div class="status-row">
        <span class="status-dot" :class="healthOk ? 'ok' : 'down'"></span>
        <strong>{{ healthOk ? 'Connected' : 'Not reachable' }}</strong>
        <span v-if="healthData" class="muted">· {{ healthData.banks }} banks, {{ healthData.bills }} bills, {{ healthData.income_sources }} income sources</span>
      </div>
      <p class="muted" style="font-size:0.85rem;margin-top:0.5rem">
        API: <code>{{ graphqlUrl }}</code> · <a :href="graphqlUrl" target="_blank" rel="noopener">Open GraphQL playground</a>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import DatabaseInfo from '../components/DatabaseInfo.vue'
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import {
  SAVE_DATABASE, LOAD_DATABASE, GET_ALL_BANKS,
  GET_SIMPLEFIN_STATUS, GET_SIMPLEFIN_ACCOUNTS,
  SETUP_SIMPLEFIN, SYNC_SIMPLEFIN_BALANCES,
  MAP_SIMPLEFIN_ACCOUNT, UNMAP_SIMPLEFIN_ACCOUNT, REMOVE_SIMPLEFIN_CONNECTION,
  GET_SNAPSHOT, GET_SIMPLEFIN_SYNCED_ACCOUNTS,
} from '../graphql/queries'
import { apolloClient } from '../graphql/client'
import PlanningSettings from '../components/PlanningSettings.vue'
import AlertSettings from '../components/AlertSettings.vue'
import DataFiles from '../components/DataFiles.vue'
import SecuritySettings from '../components/SecuritySettings.vue'
import AppearanceSettings from '../components/AppearanceSettings.vue'
import { authState } from '../utils/auth'
import SimplefinAutoSync from '../components/SimplefinAutoSync.vue'
import BackgroundJobs from '../components/BackgroundJobs.vue'
import { currency, fmtDate } from '../utils/format'
import type { Bank, SimplefinStatus, SimplefinAccount, MutationPayload } from '../types'
import { ask } from '../utils/dialog'
import Icon from '../components/Icon.vue'
import { useRoute, useRouter } from 'vue-router'

const TABS = [
  { key: 'general', label: 'General', icon: 'settings' },
  { key: 'alerts', label: 'Alerts', icon: 'bell' },
  { key: 'account', label: 'Account & users', icon: 'user' },
  { key: 'connections', label: 'Bank sync', icon: 'refresh' },
  { key: 'data', label: 'Data & backup', icon: 'download' },
]
const route = useRoute()
const router = useRouter()
const tab = computed(() => {
  const q = String(route.query.tab || '')
  return TABS.some(t => t.key === q) ? q : 'general'
})
function setTab(key: string) {
  router.replace({ query: { ...route.query, tab: key } })
}

// The Vite dev server (and production proxy) forwards /graphql to the API server
const graphqlUrl = `${window.location.origin}/graphql`

// ── Database ──
const dbMessage = ref('')
const dbSuccess = ref(false)
const saving = ref(false)
const loadingDb = ref(false)

const { mutate: doSave } = useMutation<{ saveDatabase: MutationPayload }>(SAVE_DATABASE)
const { mutate: doLoad } = useMutation<{ loadDatabase: MutationPayload & { banksCount?: number | null } }>(LOAD_DATABASE)

async function saveDb() {
  saving.value = true
  try {
    const res = await doSave()
    dbSuccess.value = res?.data?.saveDatabase?.success ?? false
    dbMessage.value = res?.data?.saveDatabase?.message ?? 'Done'
  } catch (e: any) {
    dbSuccess.value = false
    dbMessage.value = e.message
  }
  saving.value = false
}

async function loadDb() {
  loadingDb.value = true
  try {
    const res = await doLoad()
    dbSuccess.value = res?.data?.loadDatabase?.success ?? false
    dbMessage.value = res?.data?.loadDatabase?.message ?? 'Done'
  } catch (e: any) {
    dbSuccess.value = false
    dbMessage.value = e.message
  }
  loadingDb.value = false
}

// ── Health check ──
const healthOk = ref(false)
const healthData = ref<{ banks: number; bills: number; income_sources: number } | null>(null)

async function checkHealth() {
  try {
    const res = await fetch('/health')
    const data = await res.json()
    healthOk.value = data.status === 'healthy'
    healthData.value = data
  } catch {
    healthOk.value = false
    healthData.value = null
  }
}

// ── Banks (for mapping dropdowns) ──
const { result: banksResult } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)
const banks = computed(() => banksResult.value?.allBanks ?? [])

function allAccountsForBank(bankName: string): { name: string; type: string; fullName: string }[] {
  if (!bankName) return []
  const bank = banks.value.find(b => b.name === bankName)
  if (!bank) return []
  const list: { name: string; type: string; fullName: string }[] = []
  for (const a of bank.bankAccounts) list.push({ name: a.accountName, type: a.accountType, fullName: `${bankName}/${a.accountName}` })
  for (const a of bank.creditAccounts) list.push({ name: a.accountName, type: 'credit', fullName: `${bankName}/${a.accountName}` })
  if (bank.mortgageAccounts) {
    for (const a of bank.mortgageAccounts) list.push({ name: a.accountName, type: 'mortgage', fullName: `${bankName}/${a.accountName}` })
  }
  if (bank.helocAccounts) {
    for (const a of bank.helocAccounts) list.push({ name: a.accountName, type: 'heloc', fullName: `${bankName}/${a.accountName}` })
  }
  return list
}

/** Auto-detect account type when account is selected */
function onAccountSelected(sfinId: string) {
  const form = mappingForm[sfinId]
  if (!form?.bankName || !form?.accountName) return
  const accts = allAccountsForBank(form.bankName)
  const match = accts.find(a => a.name === form.accountName)
  if (match) {
    // Map the display type to our account_type enum
    if (match.type === 'credit') form.accountType = 'credit'
    else if (match.type === 'mortgage') form.accountType = 'mortgage'
    else if (match.type === 'heloc') form.accountType = 'heloc'
    else form.accountType = 'bank'
  }
}

// ── SimpleFIN Status ──
const { result: sfinStatusResult, loading: sfinLoading, refetch: refetchSfinStatus } = useQuery<{ simplefinStatus: SimplefinStatus }>(GET_SIMPLEFIN_STATUS)
const sfinStatus = computed(() => sfinStatusResult.value?.simplefinStatus ?? null)

const sfinMessage = ref('')
const sfinMsgOk = ref(false)

// ── SimpleFIN Setup ──
const sfinSetupToken = ref('')
const sfinConnecting = ref(false)
const { mutate: doSetupSfin } = useMutation<{ setupSimplefin: MutationPayload }>(SETUP_SIMPLEFIN)

async function connectSimplefin() {
  sfinConnecting.value = true
  sfinMessage.value = ''
  try {
    const res = await doSetupSfin({ variables: { setupToken: sfinSetupToken.value.trim() }})
    const d = res?.data?.setupSimplefin
    sfinMsgOk.value = d?.success ?? false
    sfinMessage.value = d?.message ?? 'Done'
    if (d?.success) {
      sfinSetupToken.value = ''
      refetchSfinStatus()
    }
  } catch (e: any) {
    sfinMsgOk.value = false
    sfinMessage.value = e.message
  }
  sfinConnecting.value = false
}

// ── SimpleFIN Accounts ──
const sfinAccounts = ref<SimplefinAccount[]>([])
const sfinFetching = ref(false)
const mappingForm = reactive<Record<string, { bankName: string; accountName: string; accountType: string }>>({})

async function fetchSfinAccounts() {
  sfinFetching.value = true
  try {
    // GraphQL errors are thrown by Apollo and surfaced in the catch below
    const { data } = await apolloClient.query<{ simplefinAccounts: SimplefinAccount[] }>({
      query: GET_SIMPLEFIN_ACCOUNTS,
      fetchPolicy: 'network-only',
    })
    const accts: SimplefinAccount[] = data?.simplefinAccounts ?? []
    sfinAccounts.value = accts
    // Initialize mapping form with current mappings
    for (const acc of accts) {
      if (!mappingForm[acc.id]) {
        mappingForm[acc.id] = {
          bankName: acc.mappedBankName ?? '',
          accountName: acc.mappedAccountName ?? '',
          accountType: acc.mappedAccountType ?? 'bank',
        }
      } else {
        // Update with latest mapping from server
        mappingForm[acc.id].bankName = acc.mappedBankName ?? mappingForm[acc.id].bankName
        mappingForm[acc.id].accountName = acc.mappedAccountName ?? mappingForm[acc.id].accountName
        mappingForm[acc.id].accountType = acc.mappedAccountType ?? mappingForm[acc.id].accountType
      }
    }
  } catch (e: unknown) {
    sfinMessage.value = `Failed to fetch accounts: ${e instanceof Error ? e.message : String(e)}`
    sfinMsgOk.value = false
  } finally {
    sfinFetching.value = false
  }
}

// Auto-fetch accounts when connected
watch(sfinStatus, (val) => {
  if (val?.isConnected && sfinAccounts.value.length === 0) {
    fetchSfinAccounts()
  }
})

// ── Mapping ──
const { mutate: doMapAccount } = useMutation<{ mapSimplefinAccount: MutationPayload }>(MAP_SIMPLEFIN_ACCOUNT)
const { mutate: doUnmapAccount } = useMutation<{ unmapSimplefinAccount: MutationPayload }>(UNMAP_SIMPLEFIN_ACCOUNT)

async function saveMapping(acc: SimplefinAccount) {
  const form = mappingForm[acc.id]
  if (!form?.bankName || !form?.accountName) return
  try {
    const res = await doMapAccount({ variables: {
      simplefinAccountId: acc.id,
      simplefinAccountName: acc.name,
      simplefinOrgName: acc.orgName,
      bankName: form.bankName,
      accountName: form.accountName,
      accountType: form.accountType,
    }})
    sfinMsgOk.value = res?.data?.mapSimplefinAccount?.success ?? false
    sfinMessage.value = res?.data?.mapSimplefinAccount?.message ?? 'Mapped'
    if (!sfinMsgOk.value) return
    refetchSfinStatus()
    fetchSfinAccounts()
  } catch (e: any) {
    sfinMsgOk.value = false
    sfinMessage.value = e.message
  }
}

async function removeMapping(accountId: string) {
  try {
    const res = await doUnmapAccount({ variables: { simplefinAccountId: accountId }})
    const d = res?.data?.unmapSimplefinAccount
    if (!d?.success) {
      sfinMsgOk.value = false
      sfinMessage.value = d?.message || 'Failed to remove mapping'
      return
    }
    if (mappingForm[accountId]) {
      mappingForm[accountId].bankName = ''
      mappingForm[accountId].accountName = ''
    }
    sfinMsgOk.value = true
    sfinMessage.value = 'Mapping removed'
    refetchSfinStatus()
    fetchSfinAccounts()
  } catch (e: any) {
    sfinMsgOk.value = false
    sfinMessage.value = e.message
  }
}

// ── Sync ──
const sfinSyncing = ref(false)
const sfinSyncMsg = ref('')
const sfinSyncOk = ref(false)
const sfinSyncDetails = ref<{ account: string; previous: number; new: number; status: string }[]>([])
const { mutate: doSyncSfin } = useMutation<{ syncSimplefinBalances: MutationPayload & { accountsUpdated?: number | null; accountsSkipped?: number | null; errors?: string[] | null; details?: unknown } }>(SYNC_SIMPLEFIN_BALANCES, {
  refetchQueries: [
    { query: GET_ALL_BANKS },
    { query: GET_SNAPSHOT },
    { query: GET_SIMPLEFIN_SYNCED_ACCOUNTS },
  ],
})

async function syncBalances() {
  sfinSyncing.value = true
  sfinSyncMsg.value = ''
  sfinSyncDetails.value = []
  try {
    const res = await doSyncSfin()
    const d = res?.data?.syncSimplefinBalances
    sfinSyncOk.value = d?.success ?? false
    sfinSyncMsg.value = d?.message ?? 'Done'
    if (d?.details) {
      try {
        const parsed = typeof d.details === 'string' ? JSON.parse(d.details) : d.details
        sfinSyncDetails.value = Array.isArray(parsed) ? parsed : []
      } catch { sfinSyncDetails.value = [] }
    }
    if (d?.success) {
      refetchSfinStatus()
      fetchSfinAccounts()
    }
  } catch (e: any) {
    sfinSyncOk.value = false
    sfinSyncMsg.value = e.message
  }
  sfinSyncing.value = false
}

// ── Disconnect ──
const { mutate: doRemoveSfin } = useMutation<{ removeSimplefinConnection: MutationPayload }>(REMOVE_SIMPLEFIN_CONNECTION)

async function disconnectSimplefin() {
  if (!(await ask('Disconnect SimpleFIN Bridge? All account mappings are removed.', { title: 'Disconnect SimpleFIN', confirmText: 'Disconnect', danger: true }))) return
  try {
    const res = await doRemoveSfin()
    const d = res?.data?.removeSimplefinConnection
    if (!d?.success) {
      sfinMsgOk.value = false
      sfinMessage.value = d?.message || 'Failed to disconnect SimpleFIN'
      return
    }
    sfinAccounts.value = []
    Object.keys(mappingForm).forEach(k => delete mappingForm[k])
    sfinMessage.value = 'SimpleFIN disconnected'
    sfinMsgOk.value = true
    sfinSyncMsg.value = ''
    refetchSfinStatus()
  } catch (e: any) {
    sfinMsgOk.value = false
    sfinMessage.value = e.message
  }
}

onMounted(() => {
  checkHealth()
})
</script>


<style scoped>
.status-row { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; font-size: 0.9rem; }
.status-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--danger); box-shadow: 0 0 0 3px var(--danger-light); }
.status-dot.ok { background: var(--success); box-shadow: 0 0 0 3px var(--success-light); }
</style>
