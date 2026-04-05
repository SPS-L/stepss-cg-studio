/**
 * sidebar.js
 * Block palette — renders categories + draggable block items from blocks.json.
 */

import { getBlocks } from './api.js';

let _catalogue = {};

export async function initSidebar(onDragStart) {
  const res = await getBlocks();
  if (!res.ok) { console.error('Could not load blocks.json:', res.error); return; }
  _catalogue = res.data;
  renderPalette(_catalogue, onDragStart);
  document.getElementById('block-search').addEventListener('input', e => {
    renderPalette(_catalogue, onDragStart, e.target.value.toLowerCase().trim());
  });
}

export function getCatalogue() { return _catalogue; }

function renderPalette(catalogue, onDragStart, filter = '') {
  const palette = document.getElementById('block-palette');
  palette.innerHTML = '';

  const groups = {};
  for (const [key, def] of Object.entries(catalogue)) {
    if (filter && !def.label.toLowerCase().includes(filter) &&
                  !key.toLowerCase().includes(filter) &&
                  !(def.description||'').toLowerCase().includes(filter)) continue;
    (groups[def.category] ||= {})[key] = def;
  }

  for (const [cat, blocks] of Object.entries(groups)) {
    const catEl = document.createElement('div');
    catEl.className = 'palette-category';
    catEl.textContent = cat;
    palette.appendChild(catEl);

    for (const [key, def] of Object.entries(blocks)) {
      const item = document.createElement('div');
      item.className = 'palette-item';
      item.draggable = true;
      item.dataset.blockType = key;
      item.title = def.description || '';
      item.innerHTML = `
        <span class="palette-dot" style="background:${def.color || '#6b7280'}"></span>
        <span class="palette-label">${def.label}</span>
      `;
      item.addEventListener('dragstart', e => {
        e.dataTransfer.setData('text/plain', key);
        e.dataTransfer.effectAllowed = 'copy';
        onDragStart && onDragStart(key, def);
      });
      palette.appendChild(item);
    }
  }

  if (palette.children.length === 0) {
    palette.innerHTML = '<div style="padding:12px;color:var(--text-dim);font-size:12px;">No blocks match.</div>';
  }
}
