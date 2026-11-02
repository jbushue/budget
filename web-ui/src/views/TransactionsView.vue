<template>
  <div>
    <div class="view-header">
      <div class="view-title">
        <h2>Transactions</h2>
        <p class="view-sub">Search, categorize and split what you've spent.</p>
      </div>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
        <button v-if="sfinConnected" class="btn btn-outline" :disabled="syncing" @click="syncSimplefin">
          <Icon name="refresh" :size="15" />
          {{ syncing ? 'Syncing...' : 'Sync' }}
        </button>
        <button class="btn btn-outline" @click="openImport"><Icon name="upload" :size="15" /> Import</button>
        <button class="btn btn-outline" :disabled="exporting" title="Download the transactions matching the filters as CSV" @click="exportCsv">
          <Icon name="download" :size="15" />
          {{ exporting ? 'Exporting...' : 'Export' }}
        </button>
        <button class="btn btn-primary" @click="openAdd"><Icon name="plus" :size="16" /> Add</button>
      </div>
    </div>

    <BillMatchSuggestions ref="matchBox" :limit="5" style="margin-bottom:1rem" @changed="refetch()" />

    <div class="card filters">
      <input v-model="filters.text" placeholder="Search description or notes..." style="flex:2;min-width:180px" />
      <select v-model="filters.category" style="flex:1;min-width:150px">
        <option value="">All categories</option>
        <option value="__none__">Uncategorized</option>
        <option v-for="c in categories" :key="c.name" :value="c.name">{{ c.name }}</option>
      </select>
      <select v-model="filters.account" style="flex:1;min-width:150px">
        <option value="">All accounts</option>
        <option v-for="a in accountOptions" :key="a" :value="a">{{ a.replace(':', ' / ') }}</option>
      </select>
      <input v-model="filters.dateFrom" type="date" title="From" />
      <input v-model="filters.dateTo" type="date" title="To" />
      <select v-if="tags.length" v-model="filters.tag" style="flex:0 1 150px">
        <option value="">All tags</option>
        <option v-for="t in tags" :key="t.tag" :value="t.tag">#{{ t.tag }} ({{ t.count }})</option>
      </select>
      <select v-model="filters.direction" style="flex:0 1 130px">
        <option value="">In &amp; out</option>
        <option value="out">Money out</option>
        <option value="in">Money in</option>
      </select>
      <input v-model.number="filters.minAmount" type="number" min="0" step="0.01" placeholder="Min $" class="amt" title="Smallest amount" />
      <input v-model.number="filters.maxAmount" type="number" min="0" step="0.01" placeholder="Max $" class="amt" title="Largest amount" />
      <button v-if="hasFilters" class="btn btn-outline btn-sm" @click="clearFilters">Clear</button>
    </div>

    <div v-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <div v-else-if="!loading && page && page.total === 0 && !hasFilters" class="empty-state">
      <div class="icon"><Icon name="transactions" :size="26" /></div>
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
                  <button v-for="tag in t.tags" :key="tag" class="tag" title="Show only this tag" @click="filters.tag = tag">#{{ tag }}</button>
                  <span v-if="t.source === 'simplefin'" class="src" title="Downloaded from SimpleFIN"><Icon name="refresh" :size="11" /></span>
                </div>
              </td>
              <td><span class="sub">{{ t.bankName ? `${t.bankName} / ${t.accountName}` : '—' }}</span></td>
              <td>
                <div class="cat-cell">
                  <button v-if="t.splits?.length" class="split-btn" :title="splitSummary(t)" @click="openDetails(t)">
                    ⑂ Split · {{ t.splits.length }} categories
                  </button>
                  <select v-else :value="t.category ?? ''" :class="{ uncat: !t.category }" @change="setCategory(t, $event.target as HTMLSelectElement)">
                    <option value="">Uncategorized</option>
                    <option v-for="c in categories" :key="c.name" :value="c.name">{{ c.name }}</option>
                  </select>
                  <button class="icon-btn edit" title="Tags, notes, split" @click="openDetails(t)">✎</button>
                </div>
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


    <!-- Add -->
    <div v-if="showAdd" class="modal-overlay" @click.self="showAdd = false">
      <div class="modal">
        <h3>Add transaction</h3>
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
        <div class="grid grid-2">
          <div class="form-group"><label>Notes</label><input v-model="addForm.notes" /></div>
          <div class="form-group"><label>Tags</label><input v-model="addForm.tags" placeholder="e.g. vacation, work" list="tag-list" /></div>
        </div>
        <p class="hint">This only records the transaction — it doesn't change account balances.</p>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showAdd = false">Cancel</button>
          <button class="btn btn-primary" :disabled="!addForm.description || !addForm.amount" @click="saveAdd">Add</button>
        </div>
      </div>
    </div>

    <datalist id="tag-list"><option v-for="t in tags" :key="t.tag" :value="t.tag" /></datalist>

    <!-- Details: tags, notes, split -->
    <div v-if="details" class="modal-overlay" @click.self="details = null">
      <div class="modal" style="max-width:620px">
        <h3>{{ details.txn.description }}</h3>
        <p class="hint">
          {{ fmtDateShort(details.txn.date) }} ·
          <strong :class="details.txn.amount < 0 ? '' : 'positive'">{{ details.txn.amount < 0 ? '−' : '+' }}{{ currency(Math.abs(details.txn.amount)) }}</strong>
          <span v-if="details.txn.bankName"> · {{ details.txn.bankName }} / {{ details.txn.accountName }}</span>
        </p>
        <div class="grid grid-2">
          <div class="form-group">
            <label>Tags</label>
            <input v-model="details.tags" placeholder="Comma separated, e.g. vacation, reimbursable" list="tag-list" />
          </div>
          <div class="form-group"><label>Notes</label><input v-model="details.notes" /></div>
        </div>

        <h4 style="margin:0.75rem 0 0.25rem">Split across categories</h4>
        <p class="hint">Put parts of one purchase in different budgets, e.g. groceries and household items from one store trip.</p>
        <div v-for="(part, i) in details.parts" :key="i" class="split-row">
          <select v-model="part.category">
            <option value="" disabled>Category</option>
            <option v-for="c in categories" :key="c.name" :value="c.name">{{ c.name }}</option>
          </select>
          <input v-model.number="part.amount" type="number" min="0" step="0.01" placeholder="Amount" />
          <input v-model="part.note" placeholder="Note (optional)" />
          <button class="icon-btn" title="Remove part" @click="details.parts.splice(i, 1)">✕</button>
        </div>
        <div class="split-foot">
          <button class="btn btn-outline btn-sm" @click="addPart"><Icon name="plus" :size="16" /> Add part</button>
          <span v-if="details.parts.length" :class="Math.abs(splitLeft) < 0.005 ? 'positive' : 'negative'">
            {{ Math.abs(splitLeft) < 0.005 ? '✓ Adds up' : splitLeft > 0 ? `${currency(splitLeft)} left to assign` : `${currency(-splitLeft)} too much` }}
          </span>
        </div>

        <div class="modal-actions">
          <button v-if="details.txn.splits?.length" class="btn btn-outline" style="margin-right:auto" @click="removeSplit">Remove split</button>
          <button class="btn btn-outline" @click="details = null">Cancel</button>
          <button class="btn btn-primary" :disabled="savingDetails || !detailsValid" @click="saveDetails">Save</button>
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
import { onRouteAction } from '../utils/routeAction'
import Icon from '../components/Icon.vue'
import { ref, reactive, computed, watch } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import { GET_ALL_BANKS, GET_SIMPLEFIN_STATUS } from '../graphql/queries'
import {
  GET_LEDGER_TRANSACTIONS, GET_CATEGORIES, ADD_LEDGER_TRANSACTION, UPDATE_LEDGER_TRANSACTION,
  DELETE_LEDGER_TRANSACTION, IMPORT_CSV_TRANSACTIONS, IMPORT_SIMPLEFIN_TRANSACTIONS, GET_TRANSACTION_TAGS,
  GET_TRANSACTIONS_CSV, SET_TRANSACTION_SPLITS,
} from '../graphql/ledger'
import { apolloClient } from '../graphql/client'
import { UNMATCH_TRANSACTION } from '../graphql/goals'
import BillMatchSuggestions from '../components/BillMatchSuggestions.vue'
import { runMutation } from '../utils/mutation'
import { currency, fmtDateShort, todayISO, splitKey } from '../utils/format'
import type {
  Bank, Category, CsvPreview, ImportResult, LedgerTransaction, MutationPayload, TagCount, TransactionPage,
} from '../types'
import { ask, notify } from '../utils/dialog'

const PAGE = 100

const EMPTY_FILTERS = {
  text: '', category: '', account: '', dateFrom: '', dateTo: '', tag: '', direction: '',
  minAmount: '' as number | '', maxAmount: '' as number | '',
}
const filters = reactive({ ...EMPTY_FILTERS })
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

const filterVars = computed(() => ({
  text: debouncedText.value || null,
  category: filters.category && filters.category !== '__none__' ? filters.category : null,
  uncategorized: filters.category === '__none__',
  account: filters.account || null,
  dateFrom: filters.dateFrom || null,
  dateTo: filters.dateTo || null,
  tag: filters.tag || null,
  direction: filters.direction || null,
  minAmount: typeof filters.minAmount === 'number' ? filters.minAmount : null,
  maxAmount: typeof filters.maxAmount === 'number' ? filters.maxAmount : null,
}))
const variables = computed(() => ({ ...filterVars.value, limit: limit.value, offset: 0 }))

const { result, loading, error, refetch } = useQuery<{ ledgerTransactions: TransactionPage }>(
  GET_LEDGER_TRANSACTIONS, () => ({ variables: variables.value, fetchPolicy: 'cache-and-network' }))
const { result: catResult } = useQuery<{ categories: Category[] }>(GET_CATEGORIES)
const { result: banksResult } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)
const { result: tagResult, refetch: refetchTags } = useQuery<{ transactionTags: TagCount[] }>(GET_TRANSACTION_TAGS)
const { result: sfinResult } = useQuery<{ simplefinStatus: { isConnected: boolean; mappedAccountCount: number } | null }>(GET_SIMPLEFIN_STATUS)

const page = computed(() => result.value?.ledgerTransactions)
const items = computed(() => page.value?.items ?? [])
const categories = computed(() => catResult.value?.categories ?? [])
const tags = computed(() => tagResult.value?.transactionTags ?? [])
const sfinConnected = computed(() => !!sfinResult.value?.simplefinStatus?.isConnected)
const accountOptions = computed(() =>
  (banksResult.value?.allBanks ?? []).flatMap(b => [
    ...b.bankAccounts.map(a => `${b.name}:${a.accountName}`),
    ...b.creditAccounts.map(a => `${b.name}:${a.accountName}`),
  ]))
const hasFilters = computed(() => Object.values(filters).some(v => v !== '' && v != null))

function clearFilters() {
  Object.assign(filters, EMPTY_FILTERS)
}

function splitTags(text: string): string[] {
  return text.split(',').map(t => t.trim()).filter(Boolean)
}

// ── Export ──
const exporting = ref(false)

async function exportCsv() {
  exporting.value = true
  try {
    const res = await apolloClient.query<{ transactionsCsv: string }>({
      query: GET_TRANSACTIONS_CSV, variables: filterVars.value, fetchPolicy: 'network-only',
    })
    const blob = new Blob([res.data?.transactionsCsv ?? ''], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `transactions-${todayISO()}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e) {
    notify(e instanceof Error ? e.message : String(e), 'error')
  } finally {
    exporting.value = false
  }
}

// ── Details: tags, notes, split ──
interface Part { category: string; amount: number | ''; note: string }
const details = ref<{ txn: LedgerTransaction; tags: string; notes: string; parts: Part[] } | null>(null)
const savingDetails = ref(false)
const { mutate: setSplitsM } = useMutation<{ setTransactionSplits: MutationPayload }>(SET_TRANSACTION_SPLITS)

function splitSummary(t: LedgerTransaction) {
  return t.splits.map(s => `${s.category}: ${currency(Math.abs(s.amount))}`).join('\n')
}

function openDetails(t: LedgerTransaction) {
  details.value = {
    txn: t, tags: (t.tags ?? []).join(', '), notes: t.notes ?? '',
    parts: (t.splits ?? []).map(s => ({ category: s.category, amount: Math.abs(s.amount), note: s.note ?? '' })),
  }
}

function addPart() {
  const d = details.value
  if (!d) return
  if (!d.parts.length) {
    d.parts.push({ category: d.txn.category ?? '', amount: Math.abs(d.txn.amount), note: '' })
    d.parts.push({ category: '', amount: 0, note: '' })
    return
  }
  d.parts.push({ category: '', amount: Math.max(0, Math.round(splitLeft.value * 100) / 100), note: '' })
}

const splitLeft = computed(() => {
  const d = details.value
  if (!d) return 0
  return Math.abs(d.txn.amount) - d.parts.reduce((sum, p) => sum + (Number(p.amount) || 0), 0)
})

const detailsValid = computed(() => {
  const d = details.value
  if (!d || !d.parts.length) return true
  return d.parts.length >= 2 && d.parts.every(p => p.category && Number(p.amount) > 0) && Math.abs(splitLeft.value) < 0.005
})

function sameSplit(t: LedgerTransaction, parts: Part[]) {
  const a = (t.splits ?? []).map(s => `${s.category}|${Math.abs(s.amount).toFixed(2)}|${s.note ?? ''}`)
  const b = parts.map(p => `${p.category}|${Number(p.amount).toFixed(2)}|${p.note}`)
  return a.join() === b.join()
}

async function saveDetails() {
  const d = details.value
  if (!d) return
  savingDetails.value = true
  try {
    const ok = await runMutation(() => updateTxn({
      variables: { id: d.txn.id, notes: d.notes, tags: splitTags(d.tags) },
    }), 'updateLedgerTransaction', { failMessage: 'Could not save' })
    if (!ok) return
    // Every part removed: back to one category (an empty split)
    const unsplit = !d.parts.length && !!d.txn.splits?.length
    if (unsplit || (d.parts.length && !sameSplit(d.txn, d.parts))) {
      const res = await runMutation(() => setSplitsM({ variables: {
        id: d.txn.id, splits: d.parts.map(p => ({ category: p.category, amount: Number(p.amount), note: p.note })),
      } }), 'setTransactionSplits', { failMessage: 'Could not save the split' })
      if (!res) return
    }
    details.value = null
    refetch()
    refetchTags()
  } finally {
    savingDetails.value = false
  }
}

async function removeSplit() {
  const d = details.value
  if (!d || !(await ask('The transaction goes back to one category (its largest part).', { title: 'Remove split', confirmText: 'Remove split', danger: true }))) return
  const res = await runMutation(() => setSplitsM({ variables: { id: d.txn.id, splits: [] } }), 'setTransactionSplits')
  if (res) {
    details.value = null
    refetch()
  }
}

function loadMore() {
  limit.value += PAGE
}

const { mutate: updateTxn } = useMutation<{ updateLedgerTransaction: MutationPayload }>(UPDATE_LEDGER_TRANSACTION)
const { mutate: deleteTxn } = useMutation<{ deleteLedgerTransaction: MutationPayload }>(DELETE_LEDGER_TRANSACTION)
const { mutate: addTxn } = useMutation<{ addLedgerTransaction: MutationPayload }>(ADD_LEDGER_TRANSACTION)
const { mutate: importCsv } = useMutation<{ importCsvTransactions: { result: ImportResult | null; previewData: CsvPreview | null } }>(IMPORT_CSV_TRANSACTIONS)
const { mutate: importSfin } = useMutation<{ importSimplefinTransactions: { result: ImportResult } }>(IMPORT_SIMPLEFIN_TRANSACTIONS)

async function setCategory(t: LedgerTransaction, el: HTMLSelectElement) {
  const category = el.value
  const res = await runMutation(() => updateTxn({
    variables: { id: t.id, category, createRule: rememberChoice.value && !!category },
  }), 'updateLedgerTransaction', { failMessage: 'Could not update category' })
  if (res) refetch()
  else el.value = t.category ?? ''  // didn't save: show what's really stored
}

const { mutate: unmatchM } = useMutation<{ unmatchTransaction: MutationPayload }>(UNMATCH_TRANSACTION)
const matchBox = ref<InstanceType<typeof BillMatchSuggestions> | null>(null)

function refreshSuggestions() {
  matchBox.value?.refetch()
}

async function unmatch(t: LedgerTransaction) {
  if (!(await ask(`Remove the ${t.matchedBill} payment recorded from this transaction?`, { title: 'Not this bill', confirmText: 'Remove', danger: true }))) return
  const res = await runMutation(() => unmatchM({ variables: { transactionId: t.id } }), 'unmatchTransaction')
  if (res) {
    refetch()
    refreshSuggestions()
  }
}

async function remove(t: LedgerTransaction) {
  if (!(await ask(`Delete "${t.description}" (${currency(t.amount)})?`, { title: 'Delete transaction', danger: true }))) return
  const res = await runMutation(() => deleteTxn({ variables: { id: t.id } }), 'deleteLedgerTransaction')
  if (res) refetch()
}

// ── Add ──
const showAdd = ref(false)
const addForm = reactive({ date: '', direction: 'out', description: '', amount: 0, category: '', account: '', notes: '', tags: '' })

function openAdd() {
  Object.assign(addForm, { date: todayISO(), direction: 'out', description: '',
    amount: 0, category: '', account: '', notes: '', tags: '' })
  showAdd.value = true
}

onRouteAction({ add: () => openAdd(), search: q => { filters.text = q } })

async function saveAdd() {
  const [bankName, accountName] = addForm.account ? splitKey(addForm.account) : ['', '']
  const res = await runMutation(() => addTxn({ variables: {
    date: addForm.date, description: addForm.description,
    amount: addForm.direction === 'out' ? -Math.abs(addForm.amount) : Math.abs(addForm.amount),
    bankName, accountName, category: addForm.category || null, notes: addForm.notes, tags: splitTags(addForm.tags),
  } }), 'addLedgerTransaction')
  if (res) {
    showAdd.value = false
    refetch()
    refetchTags()
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
  const [bankName, accountName] = splitKey(importForm.account || ':')
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
  const [bankName, accountName] = splitKey(importForm.account)
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
      notify(r?.message || 'Import failed', 'error')
      return null
    }
    let msg = r.message || 'Done'
    if (r.matchedBills) msg += `\n${r.matchedBills} bill payments recognized and marked paid.`
    if (r.errors?.length) msg += `\n${r.errors.length} rows skipped: ${r.errors.slice(0, 3).join('; ')}`
    notify(msg)
    return r
  } catch (e) {
    notify(e instanceof Error ? e.message : String(e), 'error')
    return null
  }
}
</script>

<style scoped>
.filters { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; margin-bottom: 1rem; padding: 0.75rem 1rem; }
.filters input, .filters select { margin: 0; }
.filters input[type="date"] { width: auto; flex: 0 1 165px; }
.filters .amt { width: auto; flex: 0 1 95px; }
.summary { display: flex; gap: 1.25rem; align-items: center; flex-wrap: wrap; font-size: 0.9rem; margin-bottom: 0.75rem; }
.remember { margin-left: auto; font-size: 0.8rem; color: var(--text-muted); display: flex; gap: 0.35rem; align-items: center; }
.remember input { width: auto; }
@media (max-width: 767px) {
  .remember { margin-left: 0; flex-basis: 100%; }
  .filters input[type="date"] { flex: 1 1 140px; }
}
.sub { font-size: 0.78rem; color: var(--text-muted); display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
.src { display: inline-flex; vertical-align: middle; color: var(--text-light); margin-left: 0.25rem; }
td select { padding: 0.25rem 0.4rem; font-size: 0.82rem; width: 100%; margin: 0; }
select.uncat { border-color: var(--warning); }
.icon-btn { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.85rem; }
.icon-btn:hover { color: var(--danger); }
.undo { background: none; border: none; color: inherit; text-decoration: underline; cursor: pointer; font-size: 0.7rem; padding: 0 0 0 0.25rem; }
.cat-cell { display: flex; gap: 0.25rem; align-items: center; }
.cat-cell select { flex: 1; }
.icon-btn.edit:hover { color: var(--primary); }
.split-btn { flex: 1; text-align: left; font-size: 0.8rem; padding: 0.3rem 0.45rem; border: 1px dashed var(--border); border-radius: 6px; background: transparent; color: var(--text); cursor: pointer; }
.tag { background: color-mix(in srgb, var(--primary) 12%, transparent); color: var(--primary); border: none; border-radius: 999px; padding: 0 0.45rem; font-size: 0.7rem; cursor: pointer; }
.split-row { display: grid; grid-template-columns: 1.3fr 0.8fr 1.3fr auto; gap: 0.4rem; margin-bottom: 0.4rem; align-items: center; }
.split-row input, .split-row select { margin: 0; }
.split-foot { display: flex; gap: 1rem; align-items: center; font-size: 0.85rem; margin-top: 0.25rem; }
@media (max-width: 560px) { .split-row { grid-template-columns: 1fr 1fr auto; } .split-row input:nth-of-type(2) { grid-column: 1 / 3; } }
.hint { font-size: 0.8rem; color: var(--text-muted); margin: 0.25rem 0 0.75rem; }
</style>
