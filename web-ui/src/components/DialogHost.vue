<template>
  <!-- Toasts -->
  <div class="toasts" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="t in dialogState.toasts" :key="t.id" class="toast" :class="t.kind" role="status">
        <Icon :name="ICON[t.kind]" :size="18" class="t-icon" />
        <span class="t-msg">{{ t.message }}</span>
        <button class="t-x" aria-label="Dismiss" @click="dismissToast(t.id)"><Icon name="x" :size="15" /></button>
      </div>
    </TransitionGroup>
  </div>

  <!-- Confirm / prompt -->
  <div v-if="d" class="modal-overlay" @click.self="closeDialog(d.kind === 'prompt' ? null : false)">
    <div class="modal dialog" role="alertdialog" aria-modal="true" :aria-label="d.title">
      <div class="d-head">
        <span v-if="d.kind === 'confirm'" class="d-icon" :class="{ danger: d.danger }">
          <Icon :name="d.danger ? 'alert' : 'info'" :size="20" />
        </span>
        <div style="min-width:0">
          <h3>{{ d.title }}</h3>
          <p v-if="d.message" class="d-msg">{{ d.message }}</p>
        </div>
      </div>
      <form v-if="d.kind === 'prompt'" @submit.prevent="closeDialog(d.value)">
        <input ref="input" v-model="d.value" :type="d.inputType" :placeholder="d.placeholder"
               :step="d.inputType === 'number' ? 'any' : undefined" />
      </form>
      <div class="modal-actions">
        <button class="btn btn-outline" @click="closeDialog(d.kind === 'prompt' ? null : false)">{{ d.cancelText }}</button>
        <button ref="okBtn" class="btn" :class="d.danger ? 'btn-danger' : 'btn-primary'"
                @click="closeDialog(d.kind === 'prompt' ? d.value : true)">{{ d.confirmText }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch, onMounted, onUnmounted } from 'vue'
import Icon from './Icon.vue'
import { dialogState, dismissToast, closeDialog } from '../utils/dialog'

const ICON = { success: 'checkCircle', error: 'alertCircle', warning: 'alert', info: 'info' } as const
const d = computed(() => dialogState.dialog)
const input = ref<HTMLInputElement | null>(null)
const okBtn = ref<HTMLButtonElement | null>(null)

watch(d, async v => {
  if (!v) return
  await nextTick()
  if (v.kind === 'prompt') { input.value?.focus(); input.value?.select() } else okBtn.value?.focus()
})

const onKey = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && d.value) closeDialog(d.value.kind === 'prompt' ? null : false)
}
onMounted(() => document.addEventListener('keydown', onKey))
onUnmounted(() => document.removeEventListener('keydown', onKey))
</script>

<style scoped>
.toasts {
  position: fixed; right: 1.25rem; bottom: 1.25rem; z-index: 200;
  display: flex; flex-direction: column; gap: 0.5rem; align-items: flex-end;
  pointer-events: none; max-width: min(420px, calc(100vw - 2rem));
}
.toast {
  pointer-events: auto; display: flex; align-items: flex-start; gap: 0.6rem;
  background: var(--surface); color: var(--text); border: 1px solid var(--border);
  border-radius: 10px; box-shadow: var(--shadow-lg); padding: 0.7rem 0.75rem 0.7rem 0.85rem;
  font-size: 0.875rem; line-height: 1.45; white-space: pre-line;
}
.t-icon { flex: 0 0 auto; margin-top: 1px; }
.toast.success .t-icon { color: var(--success); }
.toast.error .t-icon { color: var(--danger); }
.toast.warning .t-icon { color: var(--warning); }
.toast.info .t-icon { color: var(--primary); }
.t-msg { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.t-x { background: none; border: none; color: var(--text-light); cursor: pointer; padding: 2px; border-radius: 4px; display: grid; }
.t-x:hover { color: var(--text); background: var(--surface-hover); }
.toast-enter-active, .toast-leave-active { transition: all 0.2s ease; }
.toast-enter-from { opacity: 0; transform: translateY(8px); }
.toast-leave-to { opacity: 0; transform: translateX(16px); }

.dialog { max-width: 420px; z-index: 210; }
.d-head { display: flex; gap: 0.85rem; align-items: flex-start; }
.d-head h3 { margin-bottom: 0.35rem; }
.d-icon { flex: 0 0 40px; width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; background: var(--primary-light); color: var(--primary); }
.d-icon.danger { background: var(--danger-light); color: var(--danger); }
.d-msg { color: var(--text-muted); font-size: 0.9rem; white-space: pre-line; overflow-wrap: anywhere; }
form { margin-top: 0.75rem; }
@media (max-width: 767px) {
  .toasts { left: 0.75rem; right: 0.75rem; bottom: calc(0.75rem + env(safe-area-inset-bottom)); max-width: none; align-items: stretch; }
}
</style>
