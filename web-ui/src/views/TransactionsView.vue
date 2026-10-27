<template>
  <div>
    <div class="view-header">
      <h2>Transactions</h2>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
        <button v-if="sfinConnected" class="btn btn-outline btn-sm" :disabled="syncing" @click="syncSimplefin">
          {{ syncing ? 'Downloading...' : '⟳ Download from SimpleFIN' }}
        </button>
        <button class="btn btn-outline btn-sm" @click="openImport">⬆ Import CSV</button>
        <button class="btn btn-primary btn-sm" @click="openAdd">+ Add</button>
      </div>
    </div>

    <BillMatchSuggestions ref="matchBox" :limit="5" style="margin-bottom:1rem" @changed="refetch()" />

    <div class="card filters">
      <input v-model="filters.text" placeholder="Search description or notes..." style="flex:2;min-width:180px" />
      <select v-model="filters.category" style="flex:1;min-width:150px">
        <option value="">All categories</option>
        <option value="__none__">⚠ Uncategorized</option>
        <option v-for="c in categories" :key="c.name" :value="c.name">{{ c.name }}</option>
      </select>
      <select v-model="filters.account" style="flex:1;min-width:150px">
        <option value="">All accounts</option>
        <option v-for="a in accountOptions" :key="a" :value="a">{{ a.replace(':', ' / ') }}</option>
      </select>
      <input v-model="filters.dateFrom" type="date" title="From" />
      <input v-model="filters.dateTo" type="date" title="To" />
      <button v-if="hasFilters" class="btn btn-outline btn-sm" @click="clearFilters">Clear</button>
    </div>

    <div v-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <div v-else-if="!loading && page && page.total === 0 && !hasFilters" class="empty-state">
      <div class="icon">🧾</div>
      <p>No transactions yet.</p>
      <p style="font-size:0.85rem">
        {{ sfinConnected ? 'Download them from SimpleFIN, import' : 'Import' }} a CSV file from your bank's website,
        or add them by hand. Transactions power budgets, spending reports and the
        "learned" everyday spending on the Dashboard.
      </p>
    </div>

    <div v-else class="card">
      <div class="summary">
        <span><strong>{{ page?.total ?? 0 }}</strong> transactions</span>
        <span class="positive">In {{ currency(page?.totalIn) }}</span>
        <span class="negative">Out {{ currency(page?.totalOut) }}</span>
        <label class="remember" title="When you pick a category, also add a rule so similar transactions are categorized the same way">
          <input v-model="rememberChoice" type="checkbox" /> Remember category choices for similar transactions
        </label>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width:90px">Date</th>
              <th>Description</th>
              <th>Account</th>
              <th style="width:190px">Category</th>
              <th style="text-align:right">Amount</th>
              <th style="width:40px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in items" :key="t.id">
              <td style="white-space:nowrap">{{ fmtDateShort(t.date) }}</td>
              <td>
                <div style="font-weight:500">{{ t.description }}</div>
                <div class="sub">
                  <span v-if="t.matchedBill" class="badge badge-success" title="Recorded as this bill's payment">
                    ✓ {{ t.matchedBill }} <button class="undo" title="Not this bill — undo" @click="unmatch(t)">undo</button>
                  </span>
                  <span v-if="t.notes">{{ t.notes }}</span>
                  <span v-if="t.source !== 'manual'" class="src">{{ t.source === 'simplefin' ? 'SimpleFIN' : 'CSV' }}</span>
                </div>
              </td>
              <td class="sub">{{ t.bankName ? `${t.bankName} / ${t.accountName}` : '—' }}</td>
              <td>
                <select :value="t.category ?? ''" :class="{ uncat: !t.category }" @change="setCategory(t, ($event.target as HTMLSelectElement).value)">
                  <option value="">Uncategorized</option>
                  <option v-for="c in categories" :key="c.name" :value="c.name">{{ c.name }}</option>
                </select>
              </td>
              <td style="text-align:right;font-weight:600;white-space:nowrap" :class="t.amount < 0 ? '' : 'positive'">
                {{ t.amount < 0 ? '−' : '+' }}{{ currency(Math.abs(t.amount)) }}
              </td>
              <td><button class="icon-btn" title="Delete" @click="remove(t)">✕</button></td>
            </tr>
            <tr v-if="!items.length && !loading">
              <td colspan="6" style="text-align:center;color:var(--text-muted)">No transactions match these filters.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="loading" class="loading">Loading...</div>
      <div v-else-if="page && items.length < page.total" style="text-align:center;margin-top:0.75rem">
        <button class="btn btn-outline btn-sm" @click="loadMore">Show more ({{ page.total - items.length }} left)</button>
      </div>
    </div>

    <RecurringSuggestions ref="recurringBox" style="margin-top:1.5rem" />

    <!-- Add -->
    <div v-if="showAdd" class="modal-overlay" @click.self="showAdd = false">
      <div class="modal">
        <h3>Add Transaction</h3>
        <div class="grid grid-2">
          <div class="form-group"><label>Date</label><input v-model="addForm.date" type="date" /></div>
          <div class="form-group">
            <label>Type</label>
            <select v-model="addForm.direction">
              <option value="out">Money out (purchase)</option>
              <option value="in">Money in (deposit/refund)</option>
            </select>
          </div>
        </div>
        <div class="form-group"><label>Description</label><input v-model="addForm.description" placeholder="e.g. Kroger" /></div>
        <div class="grid grid-2">
          <div class="form-group"><label>Amount</label><input v-model.number="addForm.amount" type="number" min="0" step="0.01" /></div>
          <div class="form-group">
            <label>Category</label>
            <select v-model="addForm.category">
              <option value="">Pick automatically</option>
              <option v-for="c in categories" :key="c.name" :value="c.name">{{ c.name }}</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label>Account (optional)</label>
          <select v-model="addForm.account">
            <option value="">—</option>
            <option v-for="a in accountOptions" :key="a" :value="a">{{ a.replace(':', ' / ') }}</option>
          </select>
        </div>
        <div class="form-group"><label>Notes</label><input v-model="addForm.notes" /></div>
        <p class="hint">This only records the transaction — it doesn't change account balances.</p>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showAdd = false">Cancel</button>
          <button class="btn btn-primary" :disabled="!addForm.description || !addForm.amount" @click="saveAdd">Add</button>
        </div>
      </div>
    </div>

    <!-- CSV import -->
    <div v-if="showImport" class="modal-overlay" @click.self="showImport = false">
      <div class="modal" style="max-width:780px">
        <h3>Import transactions from a CSV file</h3>
        <p class="hint">
          Download a CSV from your bank's website (usually under "Download" or "Export" on the
          account activity page). Transactions already imported are skipped automatically.
        </p>
        <div class="grid grid-2">
          <div class="form-group">
            <label>Account these transactions belong to</label>
            <select v-model="importForm.account">
              <option value="" disabled>Choose an account</option>
              <option v-for="a in accountOptions" :key="a" :value="a">{{ a.replace(':', ' / ') }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>CSV file</label>
            <input type="file" accept=".csv,.txt,text/csv" @change="onFile" />
          </div>
        </div>

        <template v-if="preview">
          <div class="grid grid-4">
            <div v-for="f in mapFields" :key="f.key" class="form-group">
              <label>{{ f.label }}</label>
              <select v-model="mapping[f.key]" @change="refreshPreview()">
                <option :value="''">{{ f.optional ? '(none)' : '—' }}</option>
                <option v-for="(col, i) in preview.columns" :key="i" :value="i">{{ col || `Column ${i + 1}` }}</option>
              </select>
            </div>
          </div>
          <label style="font-size:0.85rem;display:flex;gap:0.4rem;align-items:center;margin-bottom:0.75rem">
            <input v-model="importForm.invert" type="checkbox" @change="refreshPreview()" />
            Purchases show as positive numbers in this file (flip the signs)
          </label>
          <div class="table-wrap" style="max-height:260px;overflow:auto">
            <table>
              <thead><tr><th>Date</th><th>Description</th><th>Category</th><th style="text-align:right">Amount</th></tr></thead>
              <tbody>
                <tr v-for="(r, i) in preview.rows" :key="i">
                  <td>{{ fmtDateShort(r.date) }}</td>
                  <td>{{ r.description }}</td>
                  <td class="sub">{{ r.category || 'Uncategorized' }}</td>
                  <td style="text-align:right" :class="r.amount < 0 ? '' : 'positive'">
                    {{ r.amount < 0 ? '−' : '+' }}{{ currency(Math.abs(r.amount)) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="hint">
            {{ preview.rowCount }} rows ready{{ preview.rowCount > preview.rows.length ? ` (first ${preview.rows.length} shown)` : '' }}.
            Check that money spent shows with a "−".
            <span v-if="preview.errors.length" class="negative"><br />{{ preview.errors.length }} rows can't be read: {{ preview.errors.slice(0, 3).join('; ') }}</span>
          </p>
        </template>
        <p v-else-if="importError" class="negative" style="font-size:0.85rem">{{ importError }}</p>

        <div class="modal-actions">
          <button class="btn btn-outline" @click="showImport = false">Cancel</button>
          <button class="btn btn-primary" :disabled="!preview || !importForm.account || importing" @click="doImport">
            {{ importing ? 'Importing...' : `Import ${preview?.rowCount ?? ''} transactions` }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import { GET_ALL_BANKS, GET_SIMPLEFIN_STATUS } from '../graphql/queries'
import {
  GET_LEDGER_TRANSACTIONS, GET_CATEGORIES, ADD_LEDGER_TRANSACTION, UPDATE_LEDGER_TRANSACTION,
  DELETE_LEDGER_TRANSACTION, IMPORT_CSV_TRANSACTIONS, IMPORT_SIMPLEFIN_TRANSACTIONS,
} from '../graphql/ledger'
import { UNMATCH_TRANSACTION } from '../graphql/goals'
import BillMatchSuggestions from '../components/BillMatchSuggestions.vue'
import RecurringSuggestions from '../components/RecurringSuggestions.vue'
import { runMutation } from '../utils/mutation'
import { currency, fmtDateShort } from '../utils/format'
import type { Bank, Category, CsvPreview, ImportResult, LedgerTransaction, MutationPayload, TransactionPage } from '../types'

const PAGE = 100

const filters = reactive({ text: '', category: '', account: '', dateFrom: '', dateTo: '' })
const limit = ref(PAGE)
const rememberChoice = ref(true)

// Debounce the search box so typing doesn't fire a query per keystroke
const debouncedText = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
watch(() => filters.text, v => {
  clearTimeout(timer)
  timer = setTimeout(() => { debouncedText.value = v }, 300)
})
watch(() => ({ ...filters }), () => { limit.value = PAGE })

const variables = computed(() => ({
  text: debouncedText.value || null,
  category: filters.category && filters.category !== '__none__' ? filters.category : null,
  uncategorized: filters.category === '__none__',
  account: filters.account || null,
  dateFrom: filters.dateFrom || null,
  dateTo: filters.dateTo || null,
  limit: limit.value,
  offset: 0,
}))

const { result, loading, error, refetch } = useQuery<{ ledgerTransactions: TransactionPage }>(
  GET_LEDGER_TRANSACTIONS, () => ({ variables: variables.value, fetchPolicy: 'cache-and-network' }))
const { result: catResult } = useQuery<{ categories: Category[] }>(GET_CATEGORIES)
const { result: banksResult } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)
const { result: sfinResult } = useQuery<{ simplefinStatus: { isConnected: boolean; mappedAccountCount: number } | null }>(GET_SIMPLEFIN_STATUS)

const page = computed(() => result.value?.ledgerTransactions)
const items = computed(() => page.value?.items ?? [])
const categories = computed(() => catResult.value?.categories ?? [])
const sfinConnected = computed(() => !!sfinResult.value?.simplefinStatus?.isConnected)
const accountOptions = computed(() =>
  (banksResult.value?.allBanks ?? []).flatMap(b => [
    ...b.bankAccounts.map(a => `${b.name}:${a.accountName}`),
    ...b.creditAccounts.map(a => `${b.name}:${a.accountName}`),
  ]))
const hasFilters = computed(() => Object.values(filters).some(Boolean))

function clearFilters() {
  Object.assign(filters, { text: '', category: '', account: '', dateFrom: '', dateTo: '' })
}

function loadMore() {
  limit.value += PAGE
}

const { mutate: updateTxn } = useMutation<{ updateLedgerTransaction: MutationPayload }>(UPDATE_LEDGER_TRANSACTION)
const { mutate: deleteTxn } = useMutation<{ deleteLedgerTransaction: MutationPayload }>(DELETE_LEDGER_TRANSACTION)
const { mutate: addTxn } = useMutation<{ addLedgerTransaction: MutationPayload }>(ADD_LEDGER_TRANSACTION)
const { mutate: importCsv } = useMutation<{ importCsvTransactions: { result: ImportResult | null; previewData: CsvPreview | null } }>(IMPORT_CSV_TRANSACTIONS)
const { mutate: importSfin } = useMutation<{ importSimplefinTransactions: { result: ImportResult } }>(IMPORT_SIMPLEFIN_TRANSACTIONS)

async function setCategory(t: LedgerTransaction, category: string) {
  const res = await runMutation(() => updateTxn({
    variables: { id: t.id, category, createRule: rememberChoice.value && !!category },
  }), 'updateLedgerTransaction', { failMessage: 'Could not update category' })
  if (res) refetch()
}

const { mutate: unmatchM } = useMutation<{ unmatchTransaction: MutationPayload }>(UNMATCH_TRANSACTION)
const matchBox = ref<InstanceType<typeof BillMatchSuggestions> | null>(null)
const recurringBox = ref<InstanceType<typeof RecurringSuggestions> | null>(null)

function refreshSuggestions() {
  matchBox.value?.refetch()
  recurringBox.value?.refetch()
}

async function unmatch(t: LedgerTransaction) {
  if (!confirm(`Remove the ${t.matchedBill} payment recorded from this transaction?`)) return
  const res = await runMutation(() => unmatchM({ variables: { transactionId: t.id } }), 'unmatchTransaction')
  if (res) {
    refetch()
    refreshSuggestions()
  }
}

async function remove(t: LedgerTransaction) {
  if (!confirm(`Delete "${t.description}" (${currency(t.amount)})?`)) return
  const res = await runMutation(() => deleteTxn({ variables: { id: t.id } }), 'deleteLedgerTransaction')
  if (res) refetch()
}

// ── Add ──
const showAdd = ref(false)
const addForm = reactive({ date: '', direction: 'out', description: '', amount: 0, category: '', account: '', notes: '' })

function openAdd() {
  Object.assign(addForm, { date: new Date().toISOString().slice(0, 10), direction: 'out', description: '',
    amount: 0, category: '', account: '', notes: '' })
  showAdd.value = true
}

async function saveAdd() {
  const [bankName, accountName] = addForm.account ? addForm.account.split(':') : ['', '']
  const res = await runMutation(() => addTxn({ variables: {
    date: addForm.date, description: addForm.description,
    amount: addForm.direction === 'out' ? -Math.abs(addForm.amount) : Math.abs(addForm.amount),
    bankName, accountName, category: addForm.category || null, notes: addForm.notes,
  } }), 'addLedgerTransaction')
  if (res) {
    showAdd.value = false
    refetch()
  }
}

// ── CSV import ──
const showImport = ref(false)
const importing = ref(false)
const importError = ref('')
const fileContent = ref('')
const preview = ref<CsvPreview | null>(null)
const importForm = reactive({ account: '', invert: false })
const mapping = reactive<Record<string, number | ''>>({ date: '', description: '', amount: '', debit: '', credit: '' })
const mapFields = [
  { key: 'date', label: 'Date column', optional: false },
  { key: 'description', label: 'Description column', optional: false },
  { key: 'amount', label: 'Amount column', optional: true },
  { key: 'debit', label: 'Or: money out column', optional: true },
  { key: 'credit', label: 'and money in column', optional: true },
]

function openImport() {
  preview.value = null
  importError.value = ''
  fileContent.value = ''
  importForm.invert = false
  if (!importForm.account && accountOptions.value.length) importForm.account = accountOptions.value[0]
  showImport.value = true
}

async function onFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  fileContent.value = await file.text()
  Object.assign(mapping, { date: '', description: '', amount: '', debit: '', credit: '' })
  await refreshPreview(true)
}

function currentMapping() {
  const m: Record<string, number> = {}
  for (const [k, v] of Object.entries(mapping)) if (v !== '' && v != null) m[k] = Number(v)
  return m
}

async function refreshPreview(auto = false) {
  if (!fileContent.value) return
  importError.value = ''
  const [bankName, accountName] = (importForm.account || ':').split(':')
  try {
    const res = await importCsv({ variables: {
      content: fileContent.value, bankName, accountName, preview: true, invert: importForm.invert,
      mapping: auto === true ? null : JSON.stringify(currentMapping()),
    } })
    const payload = res?.data?.importCsvTransactions
    if (payload?.result && !payload.result.success) {
      preview.value = null
      importError.value = payload.result.message || 'Could not read the file'
      return
    }
    const p = payload?.previewData ?? null
    preview.value = p
    if (p && auto === true) {
      const m = (typeof p.mapping === 'string' ? JSON.parse(p.mapping) : p.mapping) as Record<string, number>
      for (const k of Object.keys(mapping)) mapping[k] = m[k] ?? ''
    }
  } catch (err) {
    importError.value = err instanceof Error ? err.message : String(err)
  }
}

async function doImport() {
  const [bankName, accountName] = importForm.account.split(':')
  importing.value = true
  const res = await importResult(() => importCsv({ variables: {
    content: fileContent.value, bankName, accountName, invert: importForm.invert,
    mapping: JSON.stringify(currentMapping()),
  } }).then(r => r?.data?.importCsvTransactions.result))
  importing.value = false
  if (res) {
    showImport.value = false
    refetch()
    refreshSuggestions()
  }
}

// ── SimpleFIN ──
const syncing = ref(false)

async function syncSimplefin() {
  syncing.value = true
  const res = await importResult(() => importSfin({ variables: { days: 90 } })
    .then(r => r?.data?.importSimplefinTransactions.result))
  syncing.value = false
  if (res) {
    refetch()
    refreshSuggestions()
  }
}

/** Run an import, then tell the user what happened. Returns the result on success. */
async function importResult(run: () => Promise<ImportResult | null | undefined>): Promise<ImportResult | null> {
  try {
    const r = await run()
    if (!r || !r.success) {
      alert('Error: ' + (r?.message || 'Import failed'))
      return null
    }
    let msg = r.message || 'Done'
    if (r.matchedBills) msg += `\n${r.matchedBills} bill payments recognized and marked paid.`
    if (r.errors?.length) msg += `\n${r.errors.length} rows skipped: ${r.errors.slice(0, 3).join('; ')}`
    alert(msg)
    return r
  } catch (e) {
    alert('Error: ' + (e instanceof Error ? e.message : String(e)))
    return null
  }
}
</script>

<style scoped>
.filters { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; margin-bottom: 1rem; padding: 0.75rem 1rem; }
.filters input, .filters select { margin: 0; }
.summary { display: flex; gap: 1.25rem; align-items: center; flex-wrap: wrap; font-size: 0.9rem; margin-bottom: 0.75rem; }
.remember { margin-left: auto; font-size: 0.8rem; color: var(--text-muted); display: flex; gap: 0.35rem; align-items: center; }
.sub { font-size: 0.78rem; color: var(--text-muted); display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
.src { font-size: 0.7rem; opacity: 0.7; }
td select { padding: 0.25rem 0.4rem; font-size: 0.82rem; width: 100%; margin: 0; }
select.uncat { border-color: var(--warning); }
.icon-btn { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.85rem; }
.icon-btn:hover { color: var(--danger); }
.undo { background: none; border: none; color: inherit; text-decoration: underline; cursor: pointer; font-size: 0.7rem; padding: 0 0 0 0.25rem; }
.hint { font-size: 0.8rem; color: var(--text-muted); margin: 0.25rem 0 0.75rem; }
</style>
