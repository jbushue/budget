<template>
  <button ref="btn" class="btn btn-ghost btn-icon row-menu-btn" :class="{ open }" :aria-label="label" :title="label"
          aria-haspopup="menu" :aria-expanded="open" @click.stop="toggle">
    <Icon name="more" :size="18" :stroke="2.4" />
  </button>
  <Teleport to="body">
    <div v-if="open" ref="menu" class="row-menu" role="menu" :style="pos" @click.stop>
      <template v-for="(item, i) in visible" :key="i">
        <div v-if="item.divider" class="rm-divider"></div>
        <button class="rm-item" :class="{ danger: item.danger }" role="menuitem" :disabled="item.disabled" @click="pick(item)">
          <Icon v-if="item.icon" :name="item.icon" :size="15" />
          <span>{{ item.label }}</span>
        </button>
      </template>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref } from 'vue'
import Icon from './Icon.vue'

export interface RowMenuItem {
  label: string
  action: () => void
  icon?: string
  danger?: boolean
  disabled?: boolean
  hidden?: boolean
  divider?: boolean   // draw a line above this item
}

const props = withDefaults(defineProps<{ items: RowMenuItem[]; label?: string }>(), { label: 'More actions' })

const open = ref(false)
const btn = ref<HTMLButtonElement | null>(null)
const menu = ref<HTMLDivElement | null>(null)
const pos = ref<Record<string, string>>({})
const visible = computed(() => props.items.filter(i => !i.hidden))

function place() {
  const r = btn.value?.getBoundingClientRect()
  if (!r) return
  const h = menu.value?.offsetHeight ?? 200
  const w = menu.value?.offsetWidth ?? 200
  const below = r.bottom + 4 + h < window.innerHeight
  pos.value = {
    top: `${below ? r.bottom + 4 : Math.max(8, r.top - h - 4)}px`,
    left: `${Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8))}px`,
  }
}

async function toggle() {
  if (open.value) return close()
  document.dispatchEvent(new CustomEvent('row-menu-open'))   // only one open at a time
  open.value = true
  await nextTick()
  place()
  document.addEventListener('click', close)
  document.addEventListener('keydown', onKey)
  document.addEventListener('row-menu-open', close)
  window.addEventListener('scroll', close, true)
  window.addEventListener('resize', close)
}

function close() {
  open.value = false
  document.removeEventListener('click', close)
  document.removeEventListener('keydown', onKey)
  document.removeEventListener('row-menu-open', close)
  window.removeEventListener('scroll', close, true)
  window.removeEventListener('resize', close)
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') { close(); btn.value?.focus() }
}

function pick(item: RowMenuItem) {
  close()
  item.action()
}

onUnmounted(close)
</script>

<style>
.row-menu-btn.open { background: var(--surface-hover); color: var(--text); }
.row-menu {
  position: fixed; z-index: 150; min-width: 180px; padding: 0.3rem;
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow-lg);
  animation: pop-in 0.12s ease;
}
.rm-item {
  display: flex; align-items: center; gap: 0.55rem; width: 100%; text-align: left;
  background: none; border: none; border-radius: 6px; padding: 0.45rem 0.6rem;
  font-size: 0.85rem; font-weight: 500; color: var(--text); cursor: pointer; white-space: nowrap;
}
.rm-item svg { color: var(--text-light); }
.rm-item:hover:not(:disabled) { background: var(--surface-hover); }
.rm-item:disabled { opacity: 0.5; cursor: not-allowed; }
.rm-item.danger, .rm-item.danger svg { color: var(--danger-text); }
.rm-item.danger:hover { background: var(--danger-light); }
.rm-divider { height: 1px; background: var(--border); margin: 0.3rem 0.2rem; }
</style>
