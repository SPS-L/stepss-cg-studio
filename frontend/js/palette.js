/**
 * palette.js — left panel block library with search + collapsible categories
 */
window.Palette = (() => {
  let _blocks = {}, _collapsed = {}, _tree;

  function _render(filter='') {
    _tree.innerHTML = '';
    const cats = {};
    Object.entries(_blocks).forEach(([key, b]) => {
      const lbl = (b.label||key).toLowerCase();
      if (filter && !lbl.includes(filter) && !key.toLowerCase().includes(filter)) return;
      const cat = b.category || 'Other';
      (cats[cat] = cats[cat]||[]).push({key, b});
    });
    Object.keys(cats).sort().forEach(cat => {
      const open = !_collapsed[cat];
      const hdr = document.createElement('div');
      hdr.className = 'pal-cat';
      const arrow = document.createElement('span');
      arrow.className = 'pal-cat-arrow' + (open ? ' open' : '');
      arrow.textContent = '\u25BA';
      hdr.appendChild(arrow);
      hdr.appendChild(document.createTextNode(' ' + cat));
      const wrap = document.createElement('div');
      wrap.className = 'pal-items';
      wrap.style.display = open ? '' : 'none';
      cats[cat].forEach(({key, b}) => {
        const item = document.createElement('div');
        item.className = 'pal-item';
        item.draggable = true;
        item.dataset.blockKey = key;
        const dot = document.createElement('span');
        dot.className = 'pi-dot';
        dot.style.background = b.color || '#64748b';
        const lbl = document.createElement('span');
        lbl.className = 'pi-label';
        lbl.textContent = b.label || key;
        lbl.title = (b.description||'') + (b.args ? ' | args: ' + b.args.map(a=>a.name).join(', ') : '');
        item.append(dot, lbl);
        item.addEventListener('dragstart', e => {
          e.dataTransfer.setData('text/plain', key);
          e.dataTransfer.effectAllowed = 'copy';
        });
        wrap.appendChild(item);
      });
      hdr.addEventListener('click', () => {
        _collapsed[cat] = open;
        _render(document.getElementById('palette-search').value.trim().toLowerCase());
      });
      _tree.append(hdr, wrap);
    });
  }

  return {
    init(blocksObj) {
      _blocks = blocksObj;
      _tree   = document.getElementById('palette-tree');
      _render();
      document.getElementById('palette-search').addEventListener('input', e => {
        _render(e.target.value.trim().toLowerCase());
      });
    },
    getBlock(key) { return _blocks[key]; },
    allBlocks()   { return _blocks; }
  };
})();
