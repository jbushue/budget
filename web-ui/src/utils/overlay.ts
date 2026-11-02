/**
 * Dialogs close when you click the dim area around them (`@click.self` on
 * `.modal-overlay`). Selecting text in a field and letting go outside the
 * dialog also fires a click on the overlay, which used to close the form and
 * lose what you typed. Only count it as a click outside when the press
 * started on the overlay too.
 */
let downOn: EventTarget | null = null

export function startOverlayGuard() {
  document.addEventListener('mousedown', e => { downOn = e.target }, true)
  document.addEventListener('click', e => {
    const t = e.target as HTMLElement | null
    if (t?.classList?.contains('modal-overlay') && downOn !== t) e.stopPropagation()
  }, true)
}
