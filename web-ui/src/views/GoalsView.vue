<template>
  <div>
    <div class="view-header">
      <h2>Goals &amp; Sinking Funds</h2>
      <button class="btn btn-primary btn-sm" @click="openGoal()">+ Goal</button>
    </div>

    <p class="intro">
      Set money aside for things coming up. Money set aside in <strong>checking</strong> is kept out of the
      Dashboard's Safe to spend so you don't spend it by accident; goals in a savings account are already
      out of the way. "Set aside" only records it — move money between accounts yourself if you want to.
    </p>

    <div v-if="loading && !goals.length" class="loading">Loading goals...</div>
    <div v-else-if="error" class="card" style="color:var(--danger)">{{ error.message }}</div>

    <template v-else>
      <div v-if="suggestions.length" class="card sugg">
        <div class="card-header"><span class="card-title">💡 Bills that need saving up for</span></div>
        <p class="hint">These bills aren't paid monthly. A sinking fund spreads them out so they don't hit all at once.</p>
        <div v-for="s in suggestions" :key="s.billName" class="sugg-row">
          <div>
            <strong>{{ s.billName }}</strong> — {{ currency(s.amount) }} {{ s.frequency.replace('_', '-') }}, next due {{ fmtDate(s.nextDue) }}
            <div class="sub">Set aside about {{ currency(s.monthly) }}/month</div>
          </div>
          <button class="btn btn-primary btn-sm" @click="createFund(s)">Create sinking fund</button>
        </div>
      </div>

      <div v-if="!goals.length" class="empty-state">
        <div class="icon">🎯</div>
        <p>No goals yet. Click "+ Goal" to start one — an emergency fund, a trip, holiday gifts...</p>
      </div>

      <div class="grid grid-2">
        <div v-for="g in goals" :key="g.id" class="card goal">
          <div class="goal-head">
            <div>
              <div class="goal-name">{{ g.name }}</div>
              <div class="sub">
                <span v-if="g.linkedBill" class="badge badge-info">sinking fund · {{ g.linkedBill }}</span>
                {{ g.bankName ? `${g.bankName} / ${g.accountName}` : 'Main checking' }}
                <span v-if="g.inChecking" title="Kept out of Safe to spend">· reserved</span>
              </div>
            </div>
            <span v-if="g.complete" class="badge badge-success">✓ Funded</span>
            <span v-else-if="g.onTrack === false" class="badge badge-warning">Behind</span>
            <span v-else-if="g.onTrack" class="badge badge-success">On track</span>
          </div>
          <div class="goal-amounts">
            <span class="big">{{ currency(g.savedAmount) }}</span> of {{ currency(g.targetAmount) }}
          </div>
          <div class="progress-bar"><div class="progress-fill" :style="{ width: g.progress + '%', background: g.complete ? 'var(--success)' : 'var(--primary)' }"></div></div>
          <div class="sub" style="margin-top:0.4rem">
            <template v-if="g.complete">Ready{{ g.targetDate ? ` for ${fmtDate(g.targetDate)}` : '' }}.</template>
            <template v-else-if="g.targetDate">
              {{ currency(g.remaining) }} to go by {{ fmtDate(g.targetDate) }} —
              {{ currency(g.monthlyNeeded) }}/month<template v-if="g.perPaycheckNeeded"> or {{ currency(g.perPaycheckNeeded) }} per paycheck</template>
            </template>
            <template v-else>{{ currency(g.remaining) }} to go</template>
          </div>
          <div class="goal-actions">
            <button class="btn btn-success btn-sm" @click="contribute(g, 1)">+ Set aside</button>
            <button class="btn btn-outline btn-sm" :disabled="!g.savedAmount" @click="contribute(g, -1)">− Use</button>
            <button class="btn btn-outline btn-sm" @click="openGoal(g)">Edit</button>
            <button class="btn btn-danger btn-sm" @click="remove(g)">Delete</button>
          </div>
        </div>
      </div>
    </template>

    <div v-if="showGoal" class="modal-overlay" @click.self="showGoal = false">
      <div class="modal">
        <h3>{{ form.id ? 'Edit Goal' : 'New Goal' }}</h3>
        <div class="form-group"><label>Name</label><input v-model="form.name" placeholder="e.g. Emergency fund" /></div>
        <div class="grid grid-2">
          <div class="form-group"><label>Target amount</label><input v-model.number="form.targetAmount" type="number" min="0" step="50" /></div>
          <div class="form-group"><label>Target date (optional)</label><input v-model="form.targetDate" type="date" /></div>
        </div>
        <div class="grid grid-2">
          <div class="form-group">
            <label>Money is kept in</label>
            <select v-model="form.account">
              <option value="">Main checking</option>
              <option v-for="a in accounts" :key="a" :value="a">{{ a.replace(':', ' / ') }}</option>
            </select>
          </div>
          <div class="form-group"><label>Already set aside</label><input v-model.number="form.savedAmount" type="number" min="0" step="10" /></div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="showGoal = false">Cancel</button>
          <button class="btn btn-primary" :disabled="!form.name || !form.targetAmount" @click="save">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useQuery, useMutation } from '@vue/apollo-composable'
import { GET_ALL_BANKS } from '../graphql/queries'
import { GET_SAVINGS_GOALS, SAVE_SAVINGS_GOAL, CONTRIBUTE_TO_GOAL, DELETE_SAVINGS_GOAL, CREATE_SINKING_FUND } from '../graphql/goals'
import { runMutation } from '../utils/mutation'
import { currency, fmtDate } from '../utils/format'
import type { Bank, MutationPayload, SavingsGoal, SinkingFundSuggestion } from '../types'

const { result, loading, error, refetch } = useQuery<{ savingsGoals: SavingsGoal[]; sinkingFundSuggestions: SinkingFundSuggestion[] }>(
  GET_SAVINGS_GOALS, { fetchPolicy: 'cache-and-network' })
const { result: banksResult } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)

const goals = computed(() => result.value?.savingsGoals ?? [])
const suggestions = computed(() => result.value?.sinkingFundSuggestions ?? [])
const accounts = computed(() => (banksResult.value?.allBanks ?? []).flatMap(b =>
  b.bankAccounts.map(a => `${b.name}:${a.accountName}`)))

const { mutate: saveM } = useMutation<{ saveSavingsGoal: MutationPayload }>(SAVE_SAVINGS_GOAL)
const { mutate: contributeM } = useMutation<{ contributeToGoal: MutationPayload }>(CONTRIBUTE_TO_GOAL)
const { mutate: deleteM } = useMutation<{ deleteSavingsGoal: MutationPayload }>(DELETE_SAVINGS_GOAL)
const { mutate: fundM } = useMutation<{ createSinkingFund: MutationPayload }>(CREATE_SINKING_FUND)

const showGoal = ref(false)
const form = reactive({ id: null as number | null, name: '', targetAmount: 0, targetDate: '', account: '', savedAmount: 0 })

function openGoal(g?: SavingsGoal) {
  Object.assign(form, g
    ? { id: g.id, name: g.name, targetAmount: g.targetAmount, targetDate: g.targetDate || '',
        account: g.bankName ? `${g.bankName}:${g.accountName}` : '', savedAmount: g.savedAmount }
    : { id: null, name: '', targetAmount: 0, targetDate: '', account: '', savedAmount: 0 })
  showGoal.value = true
}

async function save() {
  const [bankName, accountName] = form.account ? form.account.split(':') : ['', '']
  const res = await runMutation(() => saveM({ variables: {
    id: form.id, name: form.name, targetAmount: form.targetAmount, targetDate: form.targetDate || null,
    bankName, accountName, savedAmount: form.savedAmount || 0,
  } }), 'saveSavingsGoal')
  if (res) {
    showGoal.value = false
    refetch()
  }
}

async function contribute(g: SavingsGoal, sign: 1 | -1) {
  const suggested = sign > 0 ? (g.perPaycheckNeeded ?? g.monthlyNeeded ?? g.remaining) : g.savedAmount
  const input = prompt(sign > 0 ? `How much are you setting aside for ${g.name}?` : `How much did you use from ${g.name}?`,
    suggested ? suggested.toFixed(2) : '')
  if (input === null) return
  const amount = parseFloat(input.replace(/[$,]/g, ''))
  if (isNaN(amount) || amount <= 0) {
    alert('Enter a dollar amount')
    return
  }
  const res = await runMutation(() => contributeM({ variables: { id: g.id, amount: sign * amount } }), 'contributeToGoal')
  if (res) refetch()
}

async function remove(g: SavingsGoal) {
  if (!confirm(`Delete the goal "${g.name}"? (No money moves.)`)) return
  const res = await runMutation(() => deleteM({ variables: { id: g.id } }), 'deleteSavingsGoal')
  if (res) refetch()
}

async function createFund(s: SinkingFundSuggestion) {
  const res = await runMutation(() => fundM({ variables: { billName: s.billName } }), 'createSinkingFund')
  if (res) refetch()
}
</script>

<style scoped>
.intro { font-size: 0.88rem; color: var(--text-muted); margin: -0.5rem 0 1.25rem; max-width: 760px; }
.hint { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 0.5rem; }
.sub { font-size: 0.8rem; color: var(--text-muted); }
.sugg { border-left: 4px solid var(--primary); margin-bottom: 1.5rem; }
.sugg-row { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 0.6rem 0; border-top: 1px solid var(--border); flex-wrap: wrap; }
.goal + .goal { margin-top: 0; }
.goal-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.6rem; }
.goal-name { font-weight: 600; font-size: 1.05rem; }
.goal-amounts { margin-bottom: 0.4rem; font-size: 0.9rem; }
.big { font-size: 1.4rem; font-weight: 700; }
.goal-actions { display: flex; gap: 0.4rem; margin-top: 0.8rem; flex-wrap: wrap; }
</style>
