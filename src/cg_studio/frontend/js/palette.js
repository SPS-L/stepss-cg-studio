/**
 * palette.js — left panel block library with search + collapsible categories
 */
window.Palette = (() => {
  let _blocks = {}, _collapsed = {}, _tree;
  let _modelType = 'exc';
  let _ramsesInputs  = {};  // { exc:[v,p,q,omega], ... }
  let _ramsesOutputs = {};  // { exc:[vf], ... }

  // Build one draggable row.
  function _item(label, color, tooltip, dragPayload) {
    const item = document.createElement('div');
    item.className = 'pal-item';
    item.draggable = true;
    const dot = document.createElement('span');
    dot.className = 'pi-dot';
    dot.style.background = color || '#64748b';
    const lbl = document.createElement('span');
    lbl.className = 'pi-label';
    lbl.textContent = label;
    lbl.title = tooltip || '';
    item.append(dot, lbl);
    item.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', dragPayload);
      e.dataTransfer.effectAllowed = 'copy';
    });
    return item;
  }

  // Synthesize the I/O category for the current model type. `ramses_in` /
  // `ramses_out` are real block types in blocks.json but each RAMSES signal
  // gets its own palette row (label = signal name). The drag payload is
  // "<type>:<name>" so the drop handler can seed the node's name/output.
  function _renderIOCategory(filter) {
    const ins  = _ramsesInputs[_modelType]  || [];
    const outs = _ramsesOutputs[_modelType] || [];
    if (!ins.length && !outs.length) return null;
    const inBlock  = _blocks['ramses_in'];
    const outBlock = _blocks['ramses_out'];
    if (!inBlock || !outBlock) return null;

    const cat = 'I/O (' + _modelType + ')';
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

    const matches = n => !filter || n.toLowerCase().includes(filter);
    ins.filter(matches).forEach(name => {
      wrap.appendChild(_item(
        name, inBlock.color,
        'RAMSES input [' + name + '] (optional source)',
        'ramses_in:' + name,
      ));
    });
    outs.filter(matches).forEach(name => {
      wrap.appendChild(_item(
        name, outBlock.color,
        'Mandatory output ' + name + ' (must be connected)',
        'ramses_out:' + name,
      ));
    });
    hdr.addEventListener('click', () => {
      _collapsed[cat] = open;
      _render(document.getElementById('palette-search').value.trim().toLowerCase());
    });
    return [hdr, wrap];
  }

  function _render(filter='') {
    _tree.innerHTML = '';

    // I/O category first (dynamic, for the current model type)
    const io = _renderIOCategory(filter);
    if (io) _tree.append(...io);

    const cats = {};
    Object.entries(_blocks).forEach(([key, b]) => {
      if (key === 'ramses_in' || key === 'ramses_out') return;  // rendered above
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
        const tooltip = (b.description||'') + (b.args ? ' | args: ' + b.args.map(a=>a.name).join(', ') : '');
        wrap.appendChild(_item(b.label||key, b.color, tooltip, key));
      });
      hdr.addEventListener('click', () => {
        _collapsed[cat] = open;
        _render(document.getElementById('palette-search').value.trim().toLowerCase());
      });
      _tree.append(hdr, wrap);
    });
  }

  return {
    init(blocksObj, opts) {
      _blocks = blocksObj;
      _tree   = document.getElementById('palette-tree');
      opts = opts || {};
      _modelType      = opts.modelType || 'exc';
      _ramsesInputs   = opts.ramsesInputs  || {};
      _ramsesOutputs  = opts.ramsesOutputs || {};
      _render();
      document.getElementById('palette-search').addEventListener('input', e => {
        _render(e.target.value.trim().toLowerCase());
      });
    },
    setModelType(mt) { _modelType = mt || 'exc'; _render(
      document.getElementById('palette-search').value.trim().toLowerCase()); },
    getBlock(key) { return _blocks[key]; },
    allBlocks()   { return _blocks; }
  };
})();
