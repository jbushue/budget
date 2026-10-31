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
      <div v-if="authState.user" class="sidebar-footer">
        <div class="nav-item user" :title="`Signed in as ${authState.user.username}`">
          <span class="nav-icon">👤</span>
          <span class="nav-label">{{ authState.user.username }}<small v-if="authState.user.is_admin"> · admin</small></span>
        </div>
        <button class="nav-item sign-out" title="Sign out" @click="logout()">
          <span class="nav-icon">🚪</span>
          <span class="nav-label">Sign out</span>
        </button>
      </div>
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
import { authState, checkAuth, logout } from './utils/auth'

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
/* Who's signed in, at the bottom of the sidebar */
.sidebar-footer { border-top: 1px solid rgba(255, 255, 255, 0.06); padding: 0.4rem 0; }
.sidebar-footer .user { cursor: default; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.sidebar-footer .user:hover { background: none; color: #94a3b8; }
.sidebar-footer small { color: #64748b; }
.sign-out { width: 100%; background: none; border-top: none; border-right: none; border-bottom: none; cursor: pointer; font: inherit; font-size: 0.875rem; text-align: left; }

/* Alert bell above every page, clear of each page's own header buttons */
.top-bar { display: flex; justify-content: flex-end; margin: -1.25rem 0 0.25rem; position: relative; z-index: 40; }
</style>
