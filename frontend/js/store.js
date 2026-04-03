/**
 * store.js — ModelProject state, undo/redo, topo-sort, signal helpers
 */
window.Store = (() => {
  function _empty() {
    return {
      model_type: 'exc', model_name: 'my_model',
      data: [], parameters: [], states: [], observables: [],
      models: [], wires: [], canvas_meta: {}
    };
  }
  let _proj = _empty(), _stack = [], _future = [];
  const MAX = 60;
  const _snap = () => JSON.stringify(_proj);
  const _push = () => { _stack.push(_snap()); if (_stack.length > MAX) _stack.shift(); _future = []; };

  return {
    get()               { return _proj; },
    set(p, save=true)   { if (save) _push(); _proj = p; },
    patch(o, save=true) { if (save) _push(); Object.assign(_proj, o); },
    reset()             { _push(); _proj = _empty(); },
    undo() {
      if (!_stack.length) return false;
      _future.push(_snap()); _proj = JSON.parse(_stack.pop()); return true;
    },
    redo() {
      if (!_future.length) return false;
      _stack.push(_snap()); _proj = JSON.parse(_future.pop()); return true;
    },
    canUndo() { return _stack.length > 0; },
    canRedo()  { return _future.length > 0; },

    addModel(node, save=true)          { if (save) _push(); _proj.models.push(node); },
    removeModel(id, save=true)         {
      if (save) _push();
      _proj.models = _proj.models.filter(m => m.id !== id);
      _proj.wires  = _proj.wires.filter(w => w.from_node !== id && w.to_node !== id);
    },
    updateModel(id, partial, save=true){
      if (save) _push();
      const m = _proj.models.find(m => m.id === id);
      if (m) Object.assign(m, partial);
    },
    addWire(w, save=true) {
      if (save) _push();
      const dup = _proj.wires.find(x =>
        x.from_node===w.from_node && x.from_port===w.from_port &&
        x.to_node===w.to_node     && x.to_port===w.to_port);
      if (!dup) _proj.wires.push(w);
    },
    removeWire(fn, fp, tn, tp, save=true) {
      if (save) _push();
      _proj.wires = _proj.wires.filter(w =>
        !(w.from_node===fn && w.from_port===fp && w.to_node===tn && w.to_port===tp));
    },

    topoSort() {
      const ids = _proj.models.map(m => m.id);
      const deg = {}, adj = {};
      ids.forEach(id => { deg[id] = 0; adj[id] = []; });
      _proj.wires.forEach(w => {
        if (adj[w.from_node] !== undefined) {
          adj[w.from_node].push(w.to_node);
          deg[w.to_node] = (deg[w.to_node]||0) + 1;
        }
      });
      const q = ids.filter(id => deg[id] === 0), out = [];
      while (q.length) {
        const cur = q.shift(); out.push(cur);
        (adj[cur]||[]).forEach(n => { if (--deg[n] === 0) q.push(n); });
      }
      return out.length === ids.length ? out : null;
    },

    freshSignal(pfx='x') {
      const used = new Set();
      _proj.models.forEach(m => (m.outputs||[]).forEach(o => used.add(o)));
      _proj.states.forEach(s => used.add(s.name));
      _proj.observables.forEach(o => used.add(o.name));
      let i = 1;
      while (used.has(`${pfx}${i}`)) i++;
      return `${pfx}${i}`;
    },

    addRow(sec, row, save=true)        { if (save) _push(); _proj[sec].push(row); },
    updateRow(sec, i, p, save=true)    { if (save) _push(); Object.assign(_proj[sec][i], p); },
    removeRow(sec, i, save=true)       { if (save) _push(); _proj[sec].splice(i,1); },

    nextId() {
      return 'n' + Date.now().toString(36) + Math.random().toString(36).slice(2,5);
    }
  };
})();
