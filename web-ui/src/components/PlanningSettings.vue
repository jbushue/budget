<template>
  <div class="card">
    <div class="card-header"><span class="card-title">Planning</span></div>
    <p style="font-size:0.85rem;color:var(--text-muted);margin:0 0 1rem">
      These drive the Dashboard's <strong>Safe to spend</strong> number and every projection.
    </p>
    <div v-if="!form" class="loading">Loading settings...</div>
    <template v-else>
      <div class="grid grid-2">
        <div class="form-group">
          <label>Cushion to keep in checking</label>
          <input v-model.number="form.cushion" type="number" min="0" step="10" />
          <small class="help">Safe-to-spend never dips into this. A small buffer for surprises.</small>
        </div>
        <div class="form-group">
          <label>Plan to follow</label>
          <select v-model="form.optimizer_goal">
            <option value="maximize_discretionary">Most cash: pay bills on time, keep money on hand</option>
            <option value="minimize_interest">Least interest: pay costly debt early</option>
            <option value="payoff_credit_account">Pay off a card: spare cash to one card</option>
          </select>
          <small class="help">Bills, Safe to spend, the timeline, alerts and the email all follow this plan.</small>
        </div>
        <div v-if="form.optimizer_goal === 'payoff_credit_account'" class="form-group">
          <label>Card to pay off</label>
          <select v-model="form.optimizer_target">
            <option v-for="c in cards" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Look ahead (days)</label>
          <input v-model.number="form.lookahead_days" type="number" min="30" max="365" step="15" />
          <small class="help">Safe to spend leaves money for every bill and promo payment this far ahead, not just until payday.</small>
        </div>
        <div class="form-group">
          <label>Everyday spending comes from</label>
          <select v-model="form.spending_account">
            <option value="">Main checking account</option>
            <option v-for="a in checkingAccounts" :key="a" :value="a">{{ a.replace(':', ' / ') }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Everyday spending (groceries, gas, eating out — anything that isn't a bill)</label>
          <select v-model="form.spending_mode">
            <option value="manual">I'll enter a weekly amount</option>
            <option value="learned">Learn it from my transactions</option>
          </select>
          <small v-if="form.spending_mode === 'learned'" class="help">
            Uses the average of the last 8 weeks of spending in "everyday" categories (see Budgets).
            Until there's enough history, the weekly amount below is used.
          </small>
        </div>
        <div class="form-group">
          <label>Weekly everyday spending</label>
          <input v-model.number="form.everyday_weekly" type="number" min="0" step="10" />
          <small class="help">About {{ currency((form.everyday_weekly || 0) / 7) }}/day, {{ currency((form.everyday_weekly || 0) * 52 / 12) }}/month.</small>
        </div>
      </div>

      <h4 style="margin:0.5rem 0 0.5rem;font-size:0.9rem">Fees used in projections</h4>
      <div class="grid grid-3">
        <div class="form-group">
          <label>Card / HELOC late fee</label>
          <input v-model.number="form.card_late_fee" type="number" min="0" step="1" />
        </div>
        <div class="form-group">
          <label>Other bills' late fee</label>
          <input v-model.number="form.default_late_fee" type="number" min="0" step="1" />
          <small class="help">Each bill can override this.</small>
        </div>
        <div class="form-group">
          <label>Overdraft fee</label>
          <input v-model.number="form.overdraft_fee" type="number" min="0" step="1" />
        </div>
      </div>

      <div style="display:flex;gap:0.75rem;align-items:center">
        <button class="btn btn-primary" :disabled="saving" @click="save">{{ saving ? 'Saving...' : 'Save planning settings' }}</button>
        <span v-if="saved" class="positive" style="font-size:0.85rem">✓ Saved</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useApolloClient, useMutation, useQuery } from '@vue/apollo-composable'
import { GET_ALL_BANKS, GET_SETTINGS, UPDATE_SETTINGS } from '../graphql/queries'
import { runMutation } from '../utils/mutation'
import { evictPlan } from '../utils/plan'
import { currency } from '../utils/format'
import type { AppSettings, Bank, MutationPayload } from '../types'

const FIELDS = ['cushion', 'optimizer_goal', 'optimizer_target', 'lookahead_days', 'spending_mode', 'everyday_weekly', 'spending_account',
  'card_late_fee', 'default_late_fee', 'overdraft_fee'] as const

const { result, refetch } = useQuery<{ settings: string | AppSettings }>(GET_SETTINGS, { fetchPolicy: 'network-only' })
const { result: banksResult } = useQuery<{ allBanks: Bank[] }>(GET_ALL_BANKS)
const { mutate: update } = useMutation<{ updateSettings: MutationPayload }>(UPDATE_SETTINGS)

const form = ref<Pick<AppSettings, typeof FIELDS[number]> | null>(null)
const saving = ref(false)
const saved = ref(false)

watch(result, r => {
  if (!r?.settings) return
  const s = (typeof r.settings === 'string' ? JSON.parse(r.settings) : r.settings) as AppSettings
  form.value = Object.fromEntries(FIELDS.map(k => [k, s[k]])) as Pick<AppSettings, typeof FIELDS[number]>
}, { immediate: true })

const checkingAccounts = computed(() =>
  (banksResult.value?.allBanks ?? []).flatMap(b => b.bankAccounts
    .filter(a => a.accountType === 'checking')
    .map(a => `${b.name}:${a.accountName}`)))

const cards = computed(() =>
  (banksResult.value?.allBanks ?? []).flatMap(b => b.creditAccounts.filter(c => c.balance > 0).map(c => c.accountName)))

const { resolveClient } = useApolloClient()

async function save() {
  if (!form.value) return
  saving.value = true
  saved.value = false
  const ok = await runMutation(() => update({ variables: { changes: JSON.stringify(form.value) } }),
    'updateSettings', { failMessage: 'Could not save settings' })
  saving.value = false
  if (ok) {
    saved.value = true
    // Plans and Safe to spend depend on these
    evictPlan(resolveClient().cache)
    refetch()
  }
}
</script>

<style scoped>
.help { display: block; font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem; }
</style>
