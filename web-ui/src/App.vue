<template>
  <div v-if="!authState.checked" class="loading" style="padding:3rem">Loading...</div>
  <LoginScreen v-else-if="!authState.authenticated" />
  <div v-else class="app-layout" :class="{ 'sidebar-collapsed': sidebarCollapsed, 'drawer-open': drawerOpen }">
    <!-- Phones: top bar with a menu button (the sidebar becomes a slide-in drawer) -->
    <header class="mobile-bar">
      <button class="menu-btn" aria-label="Open menu" @click="drawerOpen = true">☰</button>
      <span class="mobile-title">{{ currentLabel }}</span>
      <AlertBell />
    </header>
    <div class="drawer-backdrop" @click="drawerOpen = false"></div>

    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1 class="logo">💰 Budget</h1>
        <button class="collapse-btn desktop-only" :aria-label="sidebarCollapsed ? 'Expand menu' : 'Collapse menu'"
                @click="toggleCollapsed">
          {{ sidebarCollapsed ? '☰' : '✕' }}
        </button>
        <button class="collapse-btn mobile-only" aria-label="Close menu" @click="drawerOpen = false">✕</button>
      </div>
      <nav class="sidebar-nav">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item" active-class="active"
                    :title="item.label">
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
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AlertBell from './components/AlertBell.vue'
import LoginScreen from './components/LoginScreen.vue'
import { authState, checkAuth } from './utils/auth'

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

// Mid-size screens (tablets, small laptops) start with the icon-only sidebar;
// a choice made with the button is remembered.
const COLLAPSE_KEY = 'budget-sidebar-collapsed'
const saved = localStorage.getItem(COLLAPSE_KEY)
const sidebarCollapsed = ref(saved != null ? saved === '1' : window.innerWidth < 1200)
const drawerOpen = ref(false)

function toggleCollapsed() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem(COLLAPSE_KEY, sidebarCollapsed.value ? '1' : '0')
}

const route = useRoute()
const currentLabel = computed(() =>
  navItems.find(i => i.path !== '/' && route.path.startsWith(i.path))?.label ?? (route.path === '/' ? 'Dashboard' : 'Budget'))

// Close the drawer after navigating, and with Escape
watch(() => route.fullPath, () => { drawerOpen.value = false })
const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') drawerOpen.value = false }
onMounted(() => {
  checkAuth()
  document.addEventListener('keydown', onKey)
})
onUnmounted(() => document.removeEventListener('keydown', onKey))
</script>

<style scoped>
/* Alert bell above every page, clear of each page's own header buttons */
.top-bar { display: flex; justify-content: flex-end; margin: -1.25rem 0 0.25rem; position: relative; z-index: 40; }
</style>
