/**
 * Phones show data tables as stacked cards (see "Stacked tables" in style.css).
 * For that, every cell needs its column name: this copies each <th>'s text onto
 * the cells below it as data-label, and keeps doing so as tables re-render.
 * Tables inside an element with class "no-stack" keep their normal layout.
 */
function labelTable(table: HTMLTableElement) {
  const headRow = table.tHead?.rows[0]
  if (!headRow) return
  const labels: string[] = []
  for (const th of Array.from(headRow.cells)) {
    const text = (th.textContent || '').trim()
    for (let i = 0; i < (th.colSpan || 1); i++) labels.push(text)
  }
  const rows = [...Array.from(table.tBodies).flatMap(b => Array.from(b.rows)), ...(table.tFoot ? Array.from(table.tFoot.rows) : [])]
  for (const row of rows) {
    let col = 0
    for (const cell of Array.from(row.cells)) {
      const label = cell.colSpan > 1 ? '' : (labels[col] ?? '')
      if (cell.getAttribute('data-label') !== label) cell.setAttribute('data-label', label)
      col += cell.colSpan || 1
    }
  }
}

let scheduled = false
function labelAll() {
  scheduled = false
  document.querySelectorAll<HTMLTableElement>('.table-wrap table').forEach(labelTable)
}

export function startTableLabels() {
  const schedule = () => {
    if (!scheduled) {
      scheduled = true
      requestAnimationFrame(labelAll)
    }
  }
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true, characterData: true })
  schedule()
}
