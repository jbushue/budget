<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1 class="logo">💰 Budget</h1>
        <button class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          {{ sidebarCollapsed ? '☰' : '✕' }}
        </button>
      </div>
      <nav class="sidebar-nav">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item" active-class="active">
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>

    <!-- Main content -->
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const sidebarCollapsed = ref(false)

const navItems = [
  { path: '/', icon: '📊', label: 'Dashboard' },
  { path: '/accounts', icon: '🏦', label: 'Accounts' },
  { path: '/bills', icon: '📋', label: 'Bills' },
  { path: '/bill-groups', icon: '🎓', label: 'Loan Groups' },
  { path: '/income', icon: '💵', label: 'Income' },
  { path: '/transactions', icon: '🧾', label: 'Transactions' },
  { path: '/budgets', icon: '🎯', label: 'Budgets' },
  { path: '/goals', icon: '🐷', label: 'Goals' },
  { path: '/timeline', icon: '📅', label: 'Timeline' },
  { path: '/optimizer', icon: '⚡', label: 'Optimizer' },
  { path: '/debt-payoff', icon: '📉', label: 'Debt Payoff' },
  { path: '/scenarios', icon: '🔮', label: 'What-If' },
  { path: '/settings', icon: '⚙️', label: 'Settings' },
]
</script>
