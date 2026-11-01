import { reactive } from 'vue'

/** Whether the search / command palette (Ctrl+K) is open. */
export const paletteState = reactive({ open: false })
