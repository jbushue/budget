<template>
  <div class="card">
    <div class="card-header"><span class="card-title">Recent payments</span></div>
    <div v-if="loading && !rows.length" class="loading">Loading payment history...</div>
    <div v-else-if="error" class="callout danger">Could not load payment history: {{ error.message }}</div>
    <div v-else-if="rows.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Bill</th>
            <th style="text-align:right">Amount</th>
            <th>From</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(p, i) in rows" :key="i">
            <td style="font-weight:500">{{ billName(p.billName) }}</td>
            <td style="text-align:right">{{ currency(p.amountPaid) }}</td>
            <td style="font-size:0.8rem;color:var(--text-muted)">{{ p.sourceBank }} / {{ p.sourceAccount }}</td>
            <td style="font-size:0.8rem">{{ fmtDate(p.paymentDate) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-state"><p>No bill payments recorded yet.</p></div>
  </div>
</template>

<script setup lang="ts">
// The last bills marked paid (moved here from the dashboard)
import { computed } from 'vue'
import { useQuery } from '@vue/apollo-composable'
import { GET_BILL_PAYMENT_HISTORY } from '../graphql/queries'
import { billName, currency, fmtDate } from '../utils/format'
import type { BillPaymentHistory } from '../types'

const { result, loading, error, refetch } = useQuery<{ billPaymentHistory: BillPaymentHistory[] }>(
  GET_BILL_PAYMENT_HISTORY, { variables: { limit: 15 } })
const rows = computed(() => result.value?.billPaymentHistory ?? [])
defineExpose({ refetch })
</script>
