'use strict';
const rawToggle = document.getElementById('raw-toggle');
const rawPanel = document.getElementById('raw-panel');
if (rawToggle && rawPanel) {
  function closeRaw() {
    rawPanel.hidden = true;
    rawToggle.setAttribute('aria-expanded', 'false');
  }
  rawToggle.addEventListener('click', event => {
    event.stopPropagation();
    const open = rawPanel.hidden;
    rawPanel.hidden = !open;
    rawToggle.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('click', event => {
    if (rawPanel.hidden) return;
    if (event.target instanceof Node && (rawToggle.contains(event.target) || rawPanel.contains(event.target))) return;
    closeRaw();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeRaw();
  });
}
