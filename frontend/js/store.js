/**
 * store.js
 * Canonical ModelProject state store + Kahn's topological sort.
 * Emits custom events on the document for cross-module reactivity.
 *
 * Usage:
 *   import Store from './store.js';
 *   Store.on('change', () => { ... });
 *   Store.addBlock({ blockType: 'tf1p', ... });
 */

const RAMSES_INPUTS = {
  exc:  ['v','p','q','omega','if','vf'],
  tor:  ['p','omega','tm'],
  inj:  ['omega','vx','vy','ix','iy'],
  twop: ['omega1','omega2','vx1','vy1','vx2','vy2','ix1','iy1','ix2','iy2'],
};

const MANDATORY_OUTPUTS = {
  exc:  ['vf'],
  tor:  ['tm'],
  inj:  ['ix','iy'],
  twop: ['ix1','iy1','ix2','iy2'],
};

function _emptyProject() {
  return {
    version: 1,
    modelType: 'exc',
    modelName: 'MyModel',
    data: [],
    parameters: [],
    states: [],
    observables: [],
    blocks: [],
    canvas: { nodeMap: {}, drawflow: {} },
    errors: [],
  };
}

const Store = (() => {
  let _project = _emptyProject();
  let _nextBlockId = 1;
  const _listeners = {};

  /* ---- Event bus -------------------------------------------------------- */
  function on(event, fn)  { (_listeners[event] ||= []).push(fn); }
  function off(event, fn) { if (_listeners[event]) _listeners[event] = _listeners[event].filter(f => f !== fn); }
  function _emit(event, detail) {
    (_listeners[event] || []).forEach(fn => fn(detail));
    document.dispatchEvent(new CustomEvent('store:' + event, { detail }));
  }

  /* ---- Project access --------------------------------------------------- */
  function getProject() { return _project; }

  function setProject(p) {
    _project = p;
    _nextBlockId = Math.max(0, ...(_project.blocks.map(b => b.id || 0))) + 1;
    _emit('change', { full: true });
  }

  function reset() { _project = _emptyProject(); _nextBlockId = 1; _emit('change', { full: true }); }

  /* ---- Model meta ------------------------------------------------------- */
  function setModelMeta(type, name) {
    _project.modelType = type;
    _project.modelName = name;
    _emit('change', { field: 'meta' });
  }

  /* ---- Data table ------------------------------------------------------- */
  function setData(arr)  { _project.data = arr; _emit('change', { field: 'data' }); }

  /* ---- Parameters table ------------------------------------------------- */
  function setParameters(arr) { _project.parameters = arr; _emit('change', { field: 'parameters' }); }

  /* ---- States table ----------------------------------------------------- */
  function setStates(arr) { _project.states = arr; _emit('change', { field: 'states' }); }

  /* ---- Observables ------------------------------------------------------ */
  function setObservables(arr) { _project.observables = arr; _emit('change', { field: 'observables' }); }

  /* ---- Blocks ----------------------------------------------------------- */
  function addBlock(partial) {
    const id = _nextBlockId++;
    const name = (partial.blockType || 'blk') + id;
    const block = {
      id,
      blockType: partial.blockType || 'algeq',
      comment: partial.comment || '',
      args: partial.args || {},
      inputStates: partial.inputStates || [],
      outputState: partial.outputState || name,
      rawArgLines: [],
    };
    _project.blocks.push(block);
    _emit('change', { field: 'blocks', action: 'add', blockId: id });
    return block;
  }

  function updateBlock(id, patch) {
    const b = _project.blocks.find(b => b.id === id);
    if (!b) return;
    Object.assign(b, patch);
    _emit('change', { field: 'blocks', action: 'update', blockId: id });
  }

  function removeBlock(id) {
    _project.blocks = _project.blocks.filter(b => b.id !== id);
    _emit('change', { field: 'blocks', action: 'remove', blockId: id });
  }

  function connectBlocks(srcId, dstId, dstPortIndex) {
    const src = _project.blocks.find(b => b.id === srcId);
    const dst = _project.blocks.find(b => b.id === dstId);
    if (!src || !dst) return;
    dst.inputStates[dstPortIndex || 0] = src.outputState;
    _emit('change', { field: 'blocks', action: 'connect', srcId, dstId });
  }

  /* ---- Canvas layout ---------------------------------------------------- */
  function setNodePos(blockId, x, y) {
    _project.canvas.nodeMap[blockId] = { x, y };
  }

  function setDrawflow(df) {
    _project.canvas.drawflow = df;
  }

  /* ---- Helpers ---------------------------------------------------------- */
  function getRamsesInputs() { return RAMSES_INPUTS[_project.modelType] || []; }
  function getMandatoryOutputs() { return MANDATORY_OUTPUTS[_project.modelType] || []; }
  function getStateNames() { return _project.states.map(s => s.name); }
  function getDataNames()  { return _project.data.map(d => d.name); }

  function getAllSignals() {
    const states = getStateNames();
    const ramses = getRamsesInputs().map(v => '[' + v + ']');
    return [...new Set([...states, ...ramses])];
  }

  /* ---- Topological sort (Kahn's algorithm) ------------------------------ */
  function topoSort() {
    const blocks = _project.blocks;
    if (blocks.length === 0) return { sorted: [], cycles: [] };

    const producerOf = {};
    blocks.forEach(b => { if (b.outputState) producerOf[b.outputState] = b.id; });

    const inDeg = {};
    const adj = {};
    blocks.forEach(b => { inDeg[b.id] = 0; adj[b.id] = []; });

    blocks.forEach(b => {
      (b.inputStates || []).forEach(sig => {
        const prodId = producerOf[sig];
        if (prodId !== undefined && prodId !== b.id) {
          adj[prodId].push(b.id);
          inDeg[b.id]++;
        }
      });
    });

    const queue = blocks.filter(b => inDeg[b.id] === 0).map(b => b.id);
    const sorted = [];
    while (queue.length) {
      const id = queue.shift();
      sorted.push(id);
      (adj[id] || []).forEach(nid => {
        inDeg[nid]--;
        if (inDeg[nid] === 0) queue.push(nid);
      });
    }

    const cycleIds = blocks.map(b => b.id).filter(id => !sorted.includes(id));
    return { sorted, cycles: cycleIds };
  }

  function getSortedBlocks() {
    const { sorted, cycles } = topoSort();
    const byId = {};
    _project.blocks.forEach(b => { byId[b.id] = b; });
    return {
      blocks: sorted.map(id => byId[id]),
      cycles,
    };
  }

  return {
    on, off,
    getProject, setProject, reset,
    setModelMeta,
    setData, setParameters, setStates, setObservables,
    addBlock, updateBlock, removeBlock, connectBlocks,
    setNodePos, setDrawflow,
    getRamsesInputs, getMandatoryOutputs, getStateNames, getDataNames, getAllSignals,
    topoSort, getSortedBlocks,
    RAMSES_INPUTS, MANDATORY_OUTPUTS,
  };
})();

export default Store;
