<template>
  <div v-if="!authState.checked" class="loading" style="padding:3rem">Loading...</div>
  <LoginScreen v-else-if="!authState.authenticated" />
  <div v-else class="app-layout" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
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
      <div class="top-bar"><AlertBell /></div>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AlertBell from './components/AlertBell.vue'
import LoginScreen from './components/LoginScreen.vue'
import { authState, checkAuth } from './utils/auth'

onMounted(checkAuth)

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
  { path: '/reports', icon: '📈', label: 'Reports' },
  { path: '/settings', icon: '⚙️', label: 'Settings' },
]
</script>

<style scoped>
/* Alert bell above every page, clear of each page's own header buttons */
.top-bar { display: flex; justify-content: flex-end; margin: -1.25rem 0 0.25rem; position: relative; z-index: 40; }
</style>
