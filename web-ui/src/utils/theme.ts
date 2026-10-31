import { reactive } from 'vue'
import { Chart } from 'chart.js'

/**
 * Light / dark theme, remembered on this device. "system" follows the device's setting.
 * index.html applies the saved choice before the app loads (no white flash); this keeps it in sync.
 */
export type ThemeChoice = 'light' | 'dark' | 'system'

const KEY = 'budget-theme'
const media = window.matchMedia('(prefers-color-scheme: dark)')

function saved(): ThemeChoice {
  const v = localStorage.getItem(KEY)
  return v === 'light' || v === 'dark' ? v : 'system'
}

export const themeState = reactive({
  choice: saved(),
  dark: false,
})

function apply() {
  const dark = themeState.choice === 'dark' || (themeState.choice === 'system' && media.matches)
  themeState.dark = dark
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#070b14' : '#3b82f6')

  // Chart text and grid lines (charts drawn after this pick it up)
  try {
    Chart.defaults.color = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim()
    Chart.defaults.borderColor = dark ? 'rgba(148, 163, 184, 0.15)' : 'rgba(0, 0, 0, 0.1)'
  } catch {
    // charts keep Chart.js's colors; never let this stop the app loading
  }
}

export function setTheme(choice: ThemeChoice) {
  themeState.choice = choice
  if (choice === 'system') localStorage.removeItem(KEY)
  else localStorage.setItem(KEY, choice)
  apply()
}

export function startTheme() {
  apply()
  media.addEventListener('change', () => { if (themeState.choice === 'system') apply() })
}
