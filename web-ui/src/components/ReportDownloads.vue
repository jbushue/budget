<template>
  <div class="card">
    <div class="card-header">
      <span class="card-title">Download a report</span>
      <div class="segmented" role="radiogroup" aria-label="Period">
        <button v-for="p in PERIODS" :key="p.days" role="radio" :aria-checked="days === p.days" :class="{ active: days === p.days }" @click="days = p.days">{{ p.label }}</button>
      </div>
    </div>
    <div class="dl-list">
      <div v-for="r in REPORTS" :key="r.key" class="dl-row">
        <span class="dl-icon"><Icon :name="r.icon" :size="17" /></span>
        <span class="dl-text">
          <strong>{{ r.title }}</strong>
          <small>{{ r.description }}</small>
        </span>
        <span class="dl-actions">
          <a class="btn btn-outline btn-sm" :href="url(r.key, 'csv')">CSV</a>
          <a class="btn btn-outline btn-sm" :href="url(r.key, 'xlsx')">Excel</a>
        </span>
      </div>
      <div class="dl-row">
        <span class="dl-icon"><Icon name="calendar" :size="17" /></span>
        <span class="dl-text">
          <strong>Bills &amp; paydays calendar</strong>
          <small>Add your next six months of due dates and paydays to Google, Apple or Outlook calendar, with a reminder the day before each bill.</small>
        </span>
        <span class="dl-actions"><a class="btn btn-outline btn-sm" href="/files/calendar.ics">.ics file</a></span>
      </div>
      <div class="dl-row">
        <span class="dl-icon"><Icon name="printer" :size="17" /></span>
        <span class="dl-text">
          <strong>PDF of any page</strong>
          <small>Use Print on any page and choose “Save as PDF” — menus and buttons are left out.</small>
        </span>
        <span class="dl-actions"><button class="btn btn-outline btn-sm" @click="print">Print this page</button></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import Icon from './Icon.vue'

const PERIODS = [
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 180, label: '6 months' },
  { days: 365, label: '1 year' },
]
const REPORTS = [
  { key: 'monthly', icon: 'chart', title: 'Month by month', description: 'Projected income, payments, spending and ending balances for each month.' },
  { key: 'timeline', icon: 'calendar', title: 'Every payment and paycheck', description: 'Each projected bill, card and loan payment, paycheck and transfer, by date.' },
  { key: 'plan', icon: 'zap', title: 'Payment plan', description: 'When to pay each bill and from which account, from the Optimizer.' },
  { key: 'balances', icon: 'accounts', title: 'Daily balances', description: "Every account's projected balance at the end of each day." },
  { key: 'snapshot', icon: 'gem', title: 'Accounts today', description: 'Every account with its balance, limit and rate right now.' },
]
const days = ref(90)
const url = (kind: string, fmt: string) => `/files/reports/${kind}.${fmt}?days=${days.value}`
const print = () => window.print()
</script>

<style scoped>
.dl-list { display: flex; flex-direction: column; }
.dl-row { display: flex; align-items: center; gap: 0.85rem; padding: 0.7rem 0.15rem; }
.dl-row + .dl-row { border-top: 1px solid var(--border); }
.dl-icon { width: 34px; height: 34px; flex: 0 0 34px; border-radius: 9px; display: grid; place-items: center; background: var(--primary-light); color: var(--primary); }
.dl-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.1rem; }
.dl-text strong { font-size: 0.9rem; font-weight: 600; }
.dl-text small { font-size: 0.8rem; color: var(--text-muted); line-height: 1.4; }
.dl-actions { display: flex; gap: 0.35rem; flex-shrink: 0; }
@media (max-width: 560px) {
  .dl-row { flex-wrap: wrap; }
  .dl-actions { width: 100%; padding-left: calc(34px + 0.85rem); }
}
</style>
