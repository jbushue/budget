<template>
  <div class="card" style="margin-bottom:1.5rem">
    <div class="card-header"><span class="card-title">🎨 Appearance</span></div>
    <p class="help">Choose the theme for this device. <em>Match device</em> follows your phone or computer's light / dark setting.</p>
    <div class="theme-options" role="radiogroup" aria-label="Theme">
      <button v-for="o in OPTIONS" :key="o.value" type="button" role="radio" class="theme-option"
              :class="{ selected: themeState.choice === o.value }" :aria-checked="themeState.choice === o.value"
              @click="setTheme(o.value)">
        <span class="swatch" :class="o.value"><span></span></span>
        <span>{{ o.icon }} {{ o.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { setTheme, themeState, type ThemeChoice } from '../utils/theme'

const OPTIONS: { value: ThemeChoice; label: string; icon: string }[] = [
  { value: 'light', label: 'Light', icon: '☀️' },
  { value: 'dark', label: 'Dark', icon: '🌙' },
  { value: 'system', label: 'Match device', icon: '💻' },
]
</script>

<style scoped>
.help { font-size: 0.82rem; color: var(--text-muted); margin: 0 0 0.75rem; }
.theme-options { display: flex; gap: 0.75rem; flex-wrap: wrap; }
.theme-option {
  flex: 1 1 140px; max-width: 200px; display: flex; flex-direction: column; align-items: center; gap: 0.5rem;
  padding: 0.75rem; border: 2px solid var(--border-strong); border-radius: var(--radius-lg);
  background: var(--surface); color: var(--text); font: inherit; font-size: 0.875rem; font-weight: 600; cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.theme-option:hover { border-color: var(--primary); }
.theme-option.selected { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-light); }
.swatch { width: 100%; height: 48px; border-radius: var(--radius); border: 1px solid var(--border-strong); position: relative; overflow: hidden; }
.swatch span { position: absolute; left: 10%; top: 25%; width: 55%; height: 50%; border-radius: 4px; }
.swatch.light { background: #f0f2f5; }
.swatch.light span { background: #ffffff; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); }
.swatch.dark { background: #0b1120; }
.swatch.dark span { background: #151e2e; }
/* Half light, half dark; the inner card spans 10%-65%, so its split sits at (50-10)/55 of its width */
.swatch.system { background: linear-gradient(90deg, #f0f2f5 50%, #0b1120 50%); }
.swatch.system span { background: linear-gradient(90deg, #ffffff 72.7%, #151e2e 72.7%); }
@media (max-width: 767px) {
  .theme-options { gap: 0.5rem; }
  .theme-option { flex: 1 1 0; min-width: 0; padding: 0.6rem 0.4rem; font-size: 0.8rem; }
}
</style>
