<template>
  <div v-if="!authState.checked" class="loading" style="height:100vh">Loading...</div>
  <LoginScreen v-else-if="!authState.authenticated" />
  <div v-else class="app-layout" :class="{ 'sidebar-collapsed': sidebarCollapsed, 'drawer-open': drawerOpen }">
    <!-- Phones: top bar with a menu button (the sidebar becomes a slide-in drawer) -->
    <header class="mobile-bar">
      <button class="menu-btn" aria-label="Open menu" @click="drawerOpen = true"><Icon name="menu" :size="22" /></button>
      <span class="mobile-title">{{ current.label }}</span>
      <AlertBell dark />
    </header>
    <div class="drawer-backdrop" @click="drawerOpen = false"></div>

    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <RouterLink to="/" class="logo" style="text-decoration:none">
          <span class="logo-mark"><Icon name="logo" :size="17" :stroke="2.4" /></span>
          <span class="logo-text">Budget</span>
        </RouterLink>
        <button class="collapse-btn desktop-only" :aria-label="sidebarCollapsed ? 'Expand menu' : 'Collapse menu'"
                :title="sidebarCollapsed ? 'Expand menu' : 'Collapse menu'" @click="toggleCollapsed">
          <Icon name="panel" :size="18" />
        </button>
        <button class="collapse-btn mobile-only" aria-label="Close menu" @click="drawerOpen = false"><Icon name="x" :size="20" /></button>
      </div>
      <nav class="sidebar-nav">
        <template v-for="group in NAV" :key="group.label">
          <div v-if="group.label" class="nav-heading"><span>{{ group.label }}</span></div>
          <RouterLink v-for="item in group.items" :key="item.path" :to="item.path" class="nav-item"
                      :class="{ active: isActive(item.path) }" :title="sidebarCollapsed ? item.label : undefined">
            <span class="nav-icon"><Icon :name="item.icon" :size="18" /></span>
            <span class="nav-label">{{ item.label }}</span>
          </RouterLink>
        </template>
      </nav>
      <div v-if="authState.user" class="sidebar-footer">
        <div class="user-row" :title="`Signed in as ${authState.user.username}`">
          <span class="avatar">{{ authState.user.username.slice(0, 1).toUpperCase() }}</span>
          <span class="nav-label user-name">
            {{ authState.user.username }}
            <small>{{ authState.user.is_admin ? 'Admin' : 'Member' }}</small>
          </span>
          <button class="collapse-btn nav-label sign-out" title="Sign out" aria-label="Sign out" @click="logout()">
            <Icon name="logout" :size="17" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="main-content">
      <div class="top-bar">
        <div class="crumbs">
          <template v-if="current.group">
            <span>{{ current.group }}</span>
            <Icon name="chevronRight" :size="14" />
            <strong>{{ current.label }}</strong>
          </template>
          <span v-else>{{ today }}</span>
        </div>
        <AlertBell />
      </div>
      <div class="page">
        <div v-if="authState.user?.must_change_password" class="callout warning pw-banner">
          <Icon name="alert" :size="18" />
          <span>You're signed in with the generated admin password.
            <RouterLink to="/settings?tab=account">Change it in Settings → Account</RouterLink></span>
        </div>
        <RouterView />
      </div>
    </main>
    <DialogHost />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AlertBell from './components/AlertBell.vue'
import LoginScreen from './components/LoginScreen.vue'
import DialogHost from './components/DialogHost.vue'
import Icon from './components/Icon.vue'
import { authState, checkAuth, logout } from './utils/auth'

const NAV = [
  { label: '', items: [
    { path: '/', icon: 'dashboard', label: 'Dashboard' },
  ] },
  { label: 'Money', items: [
    { path: '/accounts', icon: 'accounts', label: 'Accounts' },
    { path: '/transactions', icon: 'transactions', label: 'Transactions' },
    { path: '/bills', icon: 'bills', label: 'Bills' },
    { path: '/income', icon: 'income', label: 'Income' },
    { path: '/bill-groups', icon: 'loans', label: 'Loan groups' },
  ] },
  { label: 'Plan', items: [
    { path: '/budgets', icon: 'budgets', label: 'Budgets' },
    { path: '/goals', icon: 'goals', label: 'Goals' },
    { path: '/subscriptions', icon: 'repeat', label: 'Subscriptions' },
    { path: '/timeline', icon: 'calendar', label: 'Timeline' },
  ] },
  { label: 'Optimize', items: [
    { path: '/optimizer', icon: 'zap', label: 'Optimizer' },
    { path: '/debt-payoff', icon: 'trendingDown', label: 'Debt payoff' },
    { path: '/scenarios', icon: 'sparkles', label: 'What-If' },
  ] },
  { label: 'Insights', items: [
    { path: '/reports', icon: 'chart', label: 'Reports' },
    { path: '/net-worth', icon: 'gem', label: 'Net worth' },
    { path: '/checkup', icon: 'health', label: 'Health check' },
  ] },
  { label: 'Manage', items: [
    { path: '/activity', icon: 'history', label: 'Activity' },
    { path: '/settings', icon: 'settings', label: 'Settings' },
  ] },
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

const today = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
const route = useRoute()
const isActive = (path: string) => path === '/' ? route.path === '/' : route.path.startsWith(path)
const current = computed(() => {
  for (const g of NAV) for (const i of g.items) if (isActive(i.path)) return { label: i.label, group: g.label }
  return { label: 'Budget', group: '' }
})
watch(() => current.value.label, label => { document.title = `${label} · Budget` }, { immediate: true })

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
.sidebar-footer { border-top: 1px solid rgba(255, 255, 255, 0.06); padding: 0.75rem 0.7rem; }
.user-row { display: flex; align-items: center; gap: 0.65rem; padding: 0.25rem 0.25rem 0.25rem 0.4rem; border-radius: 8px; }
.avatar {
  flex: 0 0 30px; width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center;
  background: linear-gradient(135deg, #334155, #1e293b); color: #e2e8f0; font-weight: 650; font-size: 0.85rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.user-name { flex: 1; min-width: 0; display: flex; flex-direction: column; line-height: 1.25; color: #e5e9f0; font-size: 0.85rem; font-weight: 550; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.user-name small { color: var(--sidebar-heading); font-size: 0.72rem; font-weight: 500; }
.sign-out { flex: 0 0 32px; }
:global(.sidebar-collapsed) .user-row { justify-content: center; padding: 0; }

/* Slim bar above every page: where you are, and the alert bell */
.top-bar {
  position: sticky; top: 0; z-index: 40;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  height: 56px; padding: 0 2.25rem;
  background: color-mix(in srgb, var(--bg) 85%, transparent);
  backdrop-filter: blur(8px);
}
.crumbs { display: flex; align-items: center; gap: 0.35rem; font-size: 0.84rem; color: var(--text-light); min-width: 0; }
.crumbs strong { color: var(--text-muted); font-weight: 550; }
@media (max-width: 1199px) { .top-bar { padding: 0 1.5rem; } }
@media (max-width: 767px) { .top-bar { display: none; } }

/* Reminder while the generated admin password is still in use */
.pw-banner { margin-bottom: 1.25rem; align-items: center; }
.pw-banner a { color: inherit; font-weight: 600; text-decoration: underline; }
</style>
