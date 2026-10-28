<template>
  <div>
    <div class="view-header">
      <h2>Budgets</h2>
      <div class="month-nav">
        <button class="btn btn-outline btn-sm" aria-label="Previous month" @click="shiftMonth(-1)">‹</button>
        <input v-model="month" type="month" />
        <button class="btn btn-outline btn-sm" :disabled="isCurrentMonth" @click="shiftMonth(1)">›</button>
      </div>
    </div>

    <div v-if="loading && !status" class="loading">Loading budgets...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else-if="status">
      <div class="grid grid-4" style="margin-bottom:1.5rem">
        <div class="stat-card">
          <div class="stat-label">Spent in budgeted categories</div>
          <div class="stat-value">{{ currency(status.totalBudgetedSpent) }}</div>
          <div class="stat-sub">of {{ currency(status.totalBudget) }} budgeted</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">All spending</div>
          <div class="stat-value">{{ currency(status.totalSpent + status.uncategorizedSpent) }}</div>
          <div class="stat-sub">Income {{ currency(status.income) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Everyday spending (learned)</div>
          <div class="stat-value">{{ learned != null ? currency(learned) + '/wk' : '—' }}</div>
          <div class="stat-sub">{{ learned != null ? 'average of the last 8 weeks' : 'needs 3+ weeks of transactions' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Uncategorized</div>
          <div class="stat-value" :class="status.uncategorizedSpent ? 'negative' : ''">{{ currency(status.uncategorizedSpent) }}</div>
          <div class="stat-sub">
            <RouterLink v-if="status.uncategorizedSpent" to="/transactions">Categorize them →</RouterLink>
            <span v-else>all sorted</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">{{ monthLabel }}</span>
          <span v-if="isCurrentMonth" style="font-size:0.8rem;color:var(--text-muted)">
            Day {{ status.daysElapsed }} of {{ status.daysInMonth }}
          </span>
        </div>
        <div v-if="!lines.length" class="empty-state" style="padding:1.5rem">
          <p>No spending or budgets for this month yet. Set a budget on any category below, or
            <RouterLink to="/transactions">add transactions</RouterLink>.</p>
        </div>
        <div v-for="line in lines" :key="line.category" class="budget-line">
          <div class="bl-head">
            <span class="dot" :style="{ background: line.color || '#94a3b8' }"></span>
            <span class="bl-name">{{ line.category }}</span>
            <span v-if="line.isEveryday" class="badge badge-info" title="Counts toward everyday spending">everyday</span>
            <span class="bl-amounts">
              <strong>{{ currency(line.spent) }}</strong>
              <template v-if="line.budget"> of {{ currency(line.budget) }}</template>
            </span>
          </div>
          <div v-if="line.budget" class="progress-bar">
            <div class="progress-fill" :style="{ width: Math.min(100, line.percent || 0) + '%', background: barColor(line) }"></div>
          </div>
          <div class="bl-foot">
            <span v-if="line.status === 'over'" class="negative">Over by {{ currency(-(line.remaining || 0)) }}</span>
            <span v-else-if="line.status === 'warning'" style="color:var(--warning)">
              {{ currency(line.remaining) }} left — on pace for {{ currency(line.projected) }}
            </span>
            <span v-else-if="line.status === 'ok'" class="positive">{{ currency(line.remaining) }} left</span>
            <span v-else style="color:var(--text-muted)">No budget</span>
            <button class="link-btn" @click="editBudget(line.category, line.budget)">{{ line.budget ? 'Change' : 'Set budget' }}</button>
          </div>
        </div>
      </div>
    </template>

    <!-- Categories -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">Categories</span>
        <button class="btn btn-primary btn-sm" @click="openCategory()">+ Category</button>
      </div>
      <p class="hint">
        <strong>Everyday</strong> categories are the spending that isn't set up as a bill (groceries, gas, eating out).
        Their recent average can drive the Dashboard's everyday spending allowance (Settings → Planning).
      </p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Type</th><th>Everyday</th><th style="text-align:right">Monthly budget</th><th></th></tr></thead>
          <tbody>
            <tr v-for="c in categories" :key="c.name">
              <td><span class="dot" :style="{ background: c.color || '#94a3b8' }"></span> {{ c.name }}</td>
              <td class="muted">{{ c.kind }}</td>
              <td>{{ c.isEveryday ? '✓' : '' }}</td>
              <td style="text-align:right">{{ c.monthlyBudget ? currency(c.monthlyBudget) : '—' }}</td>
              <td style="text-align:right;white-space:nowrap">
                <button class="btn btn-outline btn-sm" @click="openCategory(c)">Edit</button>
                <button class="btn btn-danger btn-sm" style="margin-left:0.35rem" @click="removeCategory(c)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Rules -->
    <div class="card">
      <div class="card-header"><span class="card-title">Auto-categorize rules</span></div>
      <p class="hint">
        Transactions whose description contains the text get the category. Your rules win over the built-in
        keyword list. Rules are also added when you pick a category on the Transactions page with
        "Remember" checked.
      </p>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:0.75rem">
        <input v-model="ruleForm.pattern" placeholder='Description contains... e.g. "costco gas"' style="flex:2;min-width:180px;margin:0" />
        <select v-model="ruleForm.category" style="flex:1;min-width:140px;margin:0">
          <option value="" disabled>Category</option>
          <option v-for="c in categories" :key="c.name" :value="c.name">{{ c.name }}</option>
        </select>
        <button class="btn btn-primary btn-sm" :disabled="!ruleForm.pattern || !ruleForm.category" @click="addRule">Add rule</button>
        <button class="btn btn-outline btn-sm" title="Re-run rules on uncategorized transactions" @click="recategorize">Re-run on uncategorized</button>
      </div>
      <div v-if="!rules.length" class="muted" style="font-size:0.85rem">No rules yet.</div>
      <div v-else class="table-wrap">
        <table>
          <thead><tr><th>Contains</th><th>Category</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in rules" :key="r.id">
              <td><code>{{ r.pattern }}</code></td>
              <td>{{ r.category }}</td>
              <td style="text-align:right"><button class="btn btn-outline btn-sm" @click="removeRule(r)">Remove</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Category modal -->
    <div v-if="showCategory" class="modal-overlay" @click.self="showCategory = false">
      <div class="modal">
        <h3>{{ catForm.renameFrom ? 'Edit Category' : 'Add Category' }}</h3>
        <div class="form-group"><label>Name</label><input v-model="catForm.name" /></div>
        <div class="grid grid-2">
          <div class="form-group">
            <label>Type</label>
            <select v-model="catForm.kind">
              <option value="expense">Expense</option>
              <option value="income">Income</option>
              <option value="transfer">Transfer (ignored in spending)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Color</label>
            <input v-model="catForm.color" type="color" style="height:38px;padding:2px" />
          </div>
        </div>
        <div class="form-group">
          <label>Monthly budget (optional)</label>
          <input v-model.number="catForm.monthlyBudget" type="number" min="0" step="10" :disabled="catForm.kind !== 'expense'" />
        </div>
        <label v-if="catForm.kind === 'expense'" style="display:flex;gap:0.4rem;align-items:center;font-size:0.9rem">
          <input v-model="catForm.isEveryday" type="checkbox" /> Everyday spending (not covered by a bill)
        </label>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showCategory = false">Cancel</button>
          <button class="btn btn-primary" :disabled="!catForm.name" @click="saveCategory">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import {
  GET_BUDGET_STATUS, GET_CATEGORIES, GET_CATEGORY_RULES, SAVE_CATEGORY, DELETE_CATEGORY,
  SET_CATEGORY_BUDGET, ADD_CATEGORY_RULE, DELETE_CATEGORY_RULE, RECATEGORIZE_TRANSACTIONS,
} from '../graphql/ledger'
import { runMutation } from '../utils/mutation'
import { currency } from '../utils/format'
import type { BudgetLine, BudgetStatus, Category, CategoryRule, MutationPayload } from '../types'

function monthKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

const thisMonth = monthKey(new Date())
const month = ref(thisMonth)
const isCurrentMonth = computed(() => month.value >= thisMonth)
const monthLabel = computed(() => {
  const [y, m] = month.value.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
})

function shiftMonth(delta: number) {
  const [y, m] = month.value.split('-').map(Number)
  month.value = monthKey(new Date(y, m - 1 + delta, 1))
}

const { result, loading, error, refetch } = useQuery<{ budgetStatus: BudgetStatus; learnedEverydayWeekly: number | null }>(
  GET_BUDGET_STATUS, () => ({ variables: { month: month.value }, fetchPolicy: 'cache-and-network' }))
const { result: catResult, refetch: refetchCats } = useQuery<{ categories: Category[] }>(GET_CATEGORIES)
const { result: ruleResult, refetch: refetchRules } = useQuery<{ categoryRules: CategoryRule[] }>(GET_CATEGORY_RULES)

const status = computed(() => result.value?.budgetStatus)
const learned = computed(() => result.value?.learnedEverydayWeekly ?? null)
const lines = computed(() => status.value?.lines ?? [])
const categories = computed(() => catResult.value?.categories ?? [])
const rules = computed(() => ruleResult.value?.categoryRules ?? [])

function barColor(line: BudgetLine): string {
  if (line.status === 'over') return 'var(--danger)'
  if (line.status === 'warning') return 'var(--warning)'
  return 'var(--success)'
}

function refreshAll() {
  refetch()
  refetchCats()
  refetchRules()
}

const { mutate: setBudget } = useMutation<{ setCategoryBudget: MutationPayload }>(SET_CATEGORY_BUDGET)
const { mutate: saveCat } = useMutation<{ saveCategory: MutationPayload }>(SAVE_CATEGORY)
const { mutate: deleteCat } = useMutation<{ deleteCategory: MutationPayload }>(DELETE_CATEGORY)
const { mutate: addRuleM } = useMutation<{ addCategoryRule: MutationPayload }>(ADD_CATEGORY_RULE)
const { mutate: deleteRuleM } = useMutation<{ deleteCategoryRule: MutationPayload }>(DELETE_CATEGORY_RULE)
const { mutate: recatM } = useMutation<{ recategorizeTransactions: MutationPayload }>(RECATEGORIZE_TRANSACTIONS)

async function editBudget(name: string, current: number | null) {
  const input = prompt(`Monthly budget for ${name} (blank or 0 to remove):`, current ? String(current) : '')
  if (input === null) return
  const value = parseFloat(input.replace(/[$,]/g, ''))
  if (input.trim() && (isNaN(value) || value < 0)) {
    alert('Enter a dollar amount')
    return
  }
  const res = await runMutation(() => setBudget({ variables: { name, monthlyBudget: value || null } }), 'setCategoryBudget')
  if (res) refreshAll()
}

// ── Categories ──
const showCategory = ref(false)
const catForm = reactive({ name: '', kind: 'expense', isEveryday: false, monthlyBudget: null as number | null,
  color: '#94a3b8', renameFrom: '' })

function openCategory(c?: Category) {
  Object.assign(catForm, c
    ? { name: c.name, kind: c.kind, isEveryday: c.isEveryday, monthlyBudget: c.monthlyBudget, color: c.color || '#94a3b8', renameFrom: c.name }
    : { name: '', kind: 'expense', isEveryday: true, monthlyBudget: null, color: '#94a3b8', renameFrom: '' })
  showCategory.value = true
}

async function saveCategory() {
  const res = await runMutation(() => saveCat({ variables: {
    name: catForm.name.trim(), kind: catForm.kind, isEveryday: catForm.isEveryday,
    monthlyBudget: catForm.kind === 'expense' ? (catForm.monthlyBudget || null) : null,
    color: catForm.color, renameFrom: catForm.renameFrom || null,
  } }), 'saveCategory')
  if (res) {
    showCategory.value = false
    refreshAll()
  }
}

async function removeCategory(c: Category) {
  if (!confirm(`Delete "${c.name}"? Its transactions become uncategorized and its rules are removed.`)) return
  const res = await runMutation(() => deleteCat({ variables: { name: c.name } }), 'deleteCategory')
  if (res) refreshAll()
}

// ── Rules ──
const ruleForm = reactive({ pattern: '', category: '' })

async function addRule() {
  const res = await runMutation(() => addRuleM({ variables: { pattern: ruleForm.pattern, category: ruleForm.category } }),
    'addCategoryRule', { showSuccess: true })
  if (res) {
    ruleForm.pattern = ''
    refreshAll()
  }
}

async function removeRule(r: CategoryRule) {
  const res = await runMutation(() => deleteRuleM({ variables: { id: r.id } }), 'deleteCategoryRule')
  if (res) refetchRules()
}

async function recategorize() {
  const res = await runMutation(() => recatM({ variables: { onlyUncategorized: true } }),
    'recategorizeTransactions', { showSuccess: true })
  if (res) refetch()
}
</script>

<style scoped>
.month-nav { display: flex; flex-wrap: nowrap !important; gap: 0.5rem; align-items: center; }
.month-nav input { margin: 0; width: 11rem; min-width: 0; flex: 0 1 11rem; }
.stat-sub { font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem; }
.budget-line { padding: 0.75rem 0; border-bottom: 1px solid var(--border); }
.budget-line:last-child { border-bottom: none; }
.bl-head { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem; }
.bl-name { font-weight: 500; }
.bl-amounts { margin-left: auto; font-size: 0.9rem; }
.bl-foot { display: flex; justify-content: space-between; font-size: 0.8rem; margin-top: 0.3rem; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
.link-btn { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 0.8rem; padding: 0; }
.hint { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 0.75rem; }
.muted { color: var(--text-muted); }
.card + .card { margin-top: 1.5rem; }
</style>
