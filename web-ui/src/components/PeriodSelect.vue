<template>
  <select v-model.number="planDays" style="width:auto" aria-label="How far ahead">
    <option v-for="p in PERIODS" :key="p.days" :value="p.days">{{ p.label }}</option>
  </select>
</template>

<script setup lang="ts">
// How far ahead to show. Shared by Timeline, Plan and What-if (it's one plan; this only changes how much you see).
import { PERIODS, planDays } from '../utils/plan'
</script>
