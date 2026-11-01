import { ref, watch, type Ref } from 'vue'

/** A copy of `source` that only updates after it stops changing for `ms`. */
export function refDebounced<T>(source: Ref<T>, ms = 300): Ref<T> {
  const out = ref(source.value) as Ref<T>
  let timer: ReturnType<typeof setTimeout> | undefined
  watch(source, v => {
    clearTimeout(timer)
    timer = setTimeout(() => { out.value = v }, ms)
  })
  return out
}
