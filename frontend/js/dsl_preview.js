/**
 * dsl_preview.js
 * Live DSL preview pane with syntax colouring.
 * Re-renders on every Store 'change' event via the backend /emit endpoint.
 */

import Store from './store.js';
import { emitDsl } from './api.js';

let _lastDsl = '';

export function initDslPreview() {
  document.addEventListener('store:change', async () => {
    await _refresh();
  });
}

export async function getDslText() {
  const { blocks: sortedBlocks, cycles } = Store.getSortedBlocks();
  const p = Store.getProject();
  const projectForEmit = { ...p, blocks: sortedBlocks };
  const res = await emitDsl(projectForEmit);
  if (!res.ok) return { dsl: '', error: res.error, cycles };
  return { dsl: res.data.dsl_text, error: null, cycles };
}

async function _refresh() {
  const preview = document.getElementById('dsl-editor');
  const badge   = document.getElementById('dsl-error-badge');
  if (!preview) return;

  const { dsl, error, cycles } = await getDslText();
  _lastDsl = dsl || '';

  preview.innerHTML = _highlight(_lastDsl);

  const hasIssues = error || (cycles && cycles.length > 0);
  if (badge) {
    badge.style.display = hasIssues ? '' : 'none';
    if (cycles && cycles.length > 0)
      badge.textContent = `⚠ Cycle in blocks: ${cycles.join(', ')}`;
    else if (error)
      badge.textContent = `⚠ ${error}`;
  }
}

function _highlight(text) {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/(^%\w+)/mg, '<span style="color:#f472b6;font-weight:700">$1</span>')
    .replace(/(^&\s+\w+)/mg, '<span style="color:#34d399">$1</span>')
    .replace(/(\{[\w.]+\})/g, '<span style="color:#fbbf24">$1</span>')
    .replace(/(\[[\w.]+\])/g, '<span style="color:#7dd3fc">$1</span>')
    .replace(/(![ \t][^\n]*)/g, '<span style="color:#64748b;font-style:italic">$1</span>');
}

export function getLastDsl() { return _lastDsl; }
