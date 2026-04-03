/**
 * canvas.js
 * Drawflow canvas wrapper.
 *   - Initialises Drawflow
 *   - Handles drag-from-sidebar drop → creates nodes
 *   - Handles node connection → writes signal names in Store
 *   - Handles node deletion → removes block from Store
 *   - Sugiyama auto-layout for DSL import (no canvas metadata)
 */

import Store from './store.js';
import { getCatalogue } from './sidebar.js';

let _df = null;
let _onSelect = null;

const NODE_W = 200;
const NODE_H = 80;
const H_GAP  = 120;
const V_GAP  = 60;

export function initCanvas(onSelectBlock) {
  _onSelect = onSelectBlock;
  const el = document.getElementById('drawflow');

  if (typeof Drawflow === 'undefined') {
    el.innerHTML = '<div style="padding:40px;color:var(--text-dim);text-align:center;">' +
      'Drawflow library not loaded. Check CDN in index.html.</div>';
    return;
  }

  _df = new Drawflow(el);
  _df.reroute = true;
  _df.reroute_fix_curvature = true;
  _df.force_first_input = false;
  _df.start();

  _setupDropZone(el);
  _setupDrawflowEvents();
}

function _setupDropZone(el) {
  el.addEventListener('dragover',  e => e.preventDefault());
  el.addEventListener('drop', e => {
    e.preventDefault();
    const blockType = e.dataTransfer.getData('text/plain');
    if (!blockType) return;
    const rect = el.getBoundingClientRect();
    const x = (e.clientX - rect.left - _df.canvas_x) / _df.zoom;
    const y = (e.clientY - rect.top  - _df.canvas_y) / _df.zoom;
    _addNode(blockType, x, y);
  });
}

function _addNode(blockType, x, y) {
  const cat   = getCatalogue();
  const def   = cat[blockType] || { label: blockType, color: '#6b7280', inputs: ['u'], outputs: ['y'] };
  const block = Store.addBlock({ blockType });

  const nInputs  = (def.inputs  || ['u']).length;
  const nOutputs = (def.outputs || ['y']).length;

  const nodeHtml = _buildNodeHtml(blockType, def, block);
  const dfId = _df.addNode(
    blockType,
    nInputs,
    nOutputs,
    x, y,
    blockType + ' df-node',
    { blockId: block.id },
    nodeHtml
  );

  Store.setNodePos(block.id, x, y);
  _styleNode(dfId, def.color || '#6b7280');

  setTimeout(() => {
    const nodeEl = document.querySelector(`.drawflow-node[id="node-${dfId}"]`);
    if (nodeEl) {
      nodeEl.addEventListener('click', ev => {
        ev.stopPropagation();
        _onSelect && _onSelect(block.id);
      });
    }
  }, 50);

  return dfId;
}

function _buildNodeHtml(blockType, def, block) {
  const label = (def.label || blockType).replace(/</g,'&lt;').replace(/>/g,'&gt;');
  return `<div class="df-node-inner" data-block-id="${block.id}">
    <div class="df-node-title" style="border-left:3px solid ${def.color||'#6b7280'}">${label}</div>
    <div class="df-node-state">${block.outputState}</div>
  </div>`;
}

function _styleNode(dfId, color) {
  setTimeout(() => {
    const nodeEl = document.querySelector(`.drawflow-node[id="node-${dfId}"]`);
    if (nodeEl) nodeEl.style.setProperty('--node-color', color);
  }, 10);
}

function _setupDrawflowEvents() {
  _df.on('connectionCreated', data => {
    const srcBlock = _blockByDfId(data.output_id);
    const dstBlock = _blockByDfId(data.input_id);
    if (!srcBlock || !dstBlock) return;
    const portIdx = parseInt((data.input_class || 'input_1').replace('input_', ''), 10) - 1;
    Store.connectBlocks(srcBlock.id, dstBlock.id, portIdx);
    _refreshNodeLabel(data.input_id);
  });

  _df.on('connectionRemoved', data => {
    const dstBlock = _blockByDfId(data.input_id);
    if (!dstBlock) return;
    const portIdx = parseInt((data.input_class || 'input_1').replace('input_', ''), 10) - 1;
    dstBlock.inputStates[portIdx] = '';
    Store.updateBlock(dstBlock.id, { inputStates: [...dstBlock.inputStates] });
  });

  _df.on('nodeRemoved', dfId => {
    const block = _blockByDfId(dfId);
    if (block) Store.removeBlock(block.id);
  });

  _df.on('nodeMoved', data => {
    const block = _blockByDfId(data.id);
    if (!block) return;
    const info = _df.getNodeFromId(data.id);
    if (info) Store.setNodePos(block.id, info.pos_x, info.pos_y);
  });
}

function _blockByDfId(dfId) {
  const info = _df.getNodeFromId(dfId);
  if (!info) return null;
  const bid = info.data && info.data.blockId;
  return Store.getProject().blocks.find(b => b.id === bid) || null;
}

function _refreshNodeLabel(dfId) {
  const block = _blockByDfId(dfId);
  if (!block) return;
  const el = document.querySelector(`.drawflow-node[id="node-${dfId}"] .df-node-state`);
  if (el) el.textContent = block.outputState;
}

/* ---- Sugiyama auto-layout (for DSL import, no canvas metadata) ---------- */
export function autoLayout(blocks) {
  if (!_df || blocks.length === 0) return {};

  const producerOf = {};
  blocks.forEach(b => { if (b.outputState) producerOf[b.outputState] = b.id; });

  const adj = {};
  const inDeg = {};
  blocks.forEach(b => { adj[b.id] = []; inDeg[b.id] = 0; });
  blocks.forEach(b => {
    (b.inputStates || []).forEach(sig => {
      const pid = producerOf[sig];
      if (pid !== undefined && pid !== b.id) {
        adj[pid].push(b.id);
        inDeg[b.id]++;
      }
    });
  });

  const layer = {};
  const queue = blocks.filter(b => inDeg[b.id] === 0).map(b => b.id);
  queue.forEach(id => { layer[id] = 0; });
  const order = [];
  while (queue.length) {
    const id = queue.shift();
    order.push(id);
    adj[id].forEach(nid => {
      layer[nid] = Math.max(layer[nid] || 0, (layer[id] || 0) + 1);
      inDeg[nid]--;
      if (inDeg[nid] === 0) queue.push(nid);
    });
  }
  const maxLayer = Math.max(0, ...Object.values(layer));
  blocks.filter(b => layer[b.id] === undefined).forEach(b => { layer[b.id] = maxLayer + 1; });

  const layerGroups = {};
  blocks.forEach(b => { (layerGroups[layer[b.id]] = layerGroups[layer[b.id]] || []).push(b.id); });

  const positions = {};
  for (const [l, ids] of Object.entries(layerGroups)) {
    ids.forEach((id, i) => {
      positions[id] = {
        x: 80 + parseInt(l) * (NODE_W + H_GAP),
        y: 60 + i * (NODE_H + V_GAP),
      };
    });
  }

  return positions;
}

/* ---- Rebuild canvas from a project (e.g. after DSL import) -------------- */
export function rebuildCanvas(project) {
  if (!_df) return;
  _df.clearModuleSelected();

  const blocks = project.blocks;
  const hasLayout = blocks.some(b => project.canvas.nodeMap[b.id]);
  const positions = hasLayout ? null : autoLayout(blocks);

  const dfIdOf = {};

  blocks.forEach(b => {
    const cat   = getCatalogue();
    const def   = cat[b.blockType] || { label: b.blockType, color: '#6b7280', inputs: ['u'], outputs: ['y'] };
    const pos   = hasLayout
      ? (project.canvas.nodeMap[b.id] || { x: 80, y: 80 })
      : (positions[b.id] || { x: 80, y: 80 });

    const nIn  = (def.inputs  || ['u']).length;
    const nOut = (def.outputs || ['y']).length;
    const html = _buildNodeHtml(b.blockType, def, b);

    const dfId = _df.addNode(
      b.blockType, nIn, nOut,
      pos.x, pos.y,
      b.blockType + ' df-node',
      { blockId: b.id }, html
    );
    dfIdOf[b.id] = dfId;
    _styleNode(dfId, def.color || '#6b7280');
  });

  const producerOf = {};
  blocks.forEach(b => { if (b.outputState) producerOf[b.outputState] = b.id; });

  blocks.forEach(b => {
    (b.inputStates || []).forEach((sig, portIdx) => {
      const srcId = producerOf[sig];
      if (srcId !== undefined && dfIdOf[srcId] && dfIdOf[b.id]) {
        try {
          _df.addConnection(dfIdOf[srcId], dfIdOf[b.id], 'output_1', `input_${portIdx + 1}`);
        } catch (_) {}
      }
    });
  });

  blocks.forEach(b => {
    const dfId = dfIdOf[b.id];
    setTimeout(() => {
      const nodeEl = document.querySelector(`.drawflow-node[id="node-${dfId}"]`);
      if (nodeEl) {
        nodeEl.addEventListener('click', ev => {
          ev.stopPropagation();
          _onSelect && _onSelect(b.id);
        });
      }
    }, 50);
  });
}

export function clearCanvas() {
  if (_df) {
    const data = _df.export();
    const home = data.drawflow && data.drawflow.Home && data.drawflow.Home.data;
    if (home) Object.keys(home).forEach(id => { try { _df.removeNodeId('node-' + id); } catch(_){} });
  }
}

export function exportDrawflow() {
  return _df ? _df.export() : {};
}
