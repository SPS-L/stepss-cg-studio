/**
 * canvas.js — Drawflow canvas: node CRUD, drag-drop, wiring, sync to Store
 *
 * Phase 3 additions:
 *   - sugiyamaLayout(proj) — assigns (x,y) positions when importing a DSL .txt
 *     that has no canvas metadata. Uses longest-path layering + barycentric
 *     crossing-reduction (two-pass, three iterations).
 */
window.Canvas = (() => {
  let _df, _blocks={}, _onSelect, _onChange, _selDfId=null, _loading=false;

  const LAYER_W = 300;  // horizontal spacing between layers (px)
  const GAP_Y   = 30;   // vertical gap between stacked nodes in a layer (px)
  const ORIGIN_X = 80;
  const ORIGIN_Y = 40;

  // Estimate rendered node height from port counts. Must stay rough but
  // conservative — headroom is better than overlap.
  //   header + title row ≈ 44px; each port row ≈ 28px; algeq with many
  //   connectors gets tall quickly.
  function _estimateHeight(m) {
    const nIn  = (m && m.inputs  || []).length;
    const nOut = (m && m.outputs || []).length;
    const ports = Math.max(nIn, nOut, 1);
    return 44 + ports * 28;
  }

  const _dfEl = id  => document.querySelector('#node-'+id);
  const _df2s = id  => { const el=_dfEl(id); return el?el.dataset.storeId:null; };
  const _s2df = sid => {
    const el=document.querySelector('.drawflow-node[data-store-id="'+sid+'"]');
    return el?parseInt(el.id.replace('node-','')):null;
  };

  // ── Sugiyama layout ────────────────────────────────────────────────────────
  /**
   * Given a ModelProject, returns {id -> {x, y}} for every block.
   * Steps:
   *   1. Longest-path layering (sources at layer 0, sinks at max layer).
   *   2. Three-pass barycentric crossing reduction (down, up, down).
   *   3. Map (layer, position-within-layer) → pixel coordinates.
   *
   * RAMSES models often contain feedback (integrators). Cycles are broken by
   * ignoring back-edges identified via DFS finishing order.
   */
  function sugiyamaLayout(proj) {
    const models = proj.models || [];
    if (!models.length) return {};

    const ids = models.map(m => m.id);
    const idx = {}; ids.forEach((id,i) => idx[id]=i);

    // Build adjacency (forward edges only — skip back-edges via DFS)
    const adj  = ids.map(() => []);  // adj[i] = [j, ...]
    const radj = ids.map(() => []);  // reverse
    const wires = proj.wires || [];

    // Detect back-edges with iterative DFS
    const WHITE=0,GREY=1,BLACK=2;
    const color = new Array(ids.length).fill(WHITE);
    const backEdges = new Set();
    function dfs(u) {
      const stack = [[u, 0]];  // [node, edge-index]
      color[u] = GREY;
      while (stack.length) {
        const [n, ei] = stack[stack.length-1];
        // build raw neighbours once
        if (ei === 0) {
          // neighbours determined by wires
        }
        // collect children from wires
        const children = wires
          .filter(w => w.from_node === ids[n] && idx[w.to_node] !== undefined)
          .map(w => idx[w.to_node]);
        if (ei < children.length) {
          stack[stack.length-1][1]++;
          const v = children[ei];
          if (color[v] === GREY) {
            backEdges.add(`${n}-${v}`);
          } else if (color[v] === WHITE) {
            color[v] = GREY;
            stack.push([v, 0]);
          }
        } else {
          color[n] = BLACK;
          stack.pop();
        }
      }
    }
    ids.forEach((_,i) => { if (color[i]===WHITE) dfs(i); });

    wires.forEach(w => {
      const f=idx[w.from_node], t=idx[w.to_node];
      if (f===undefined||t===undefined) return;
      if (backEdges.has(`${f}-${t}`)) return;  // skip back-edge
      adj[f].push(t);
      radj[t].push(f);
    });

    // 1. Longest-path layering
    const layer = new Array(ids.length).fill(0);
    const inDeg = radj.map(r => r.length);
    const queue = [];
    inDeg.forEach((d,i) => { if(d===0) queue.push(i); });
    const order = [];
    const tempDeg = [...inDeg];
    const q2 = [...queue];
    while (q2.length) {
      const u = q2.shift(); order.push(u);
      adj[u].forEach(v => { if(--tempDeg[v]===0) q2.push(v); });
    }
    // any remaining (cycle remnants) get appended
    ids.forEach((_,i)=>{ if(!order.includes(i)) order.push(i); });

    order.forEach(u => {
      adj[u].forEach(v => {
        if (layer[v] < layer[u]+1) layer[v] = layer[u]+1;
      });
    });

    // 2. Group nodes by layer
    const maxLayer = Math.max(...layer);
    const layers = Array.from({length:maxLayer+1}, ()=>[]);
    ids.forEach((_,i) => layers[layer[i]].push(i));

    // Assign initial positions within layer
    const pos = new Array(ids.length).fill(0);
    layers.forEach(grp => grp.forEach((n,p) => { pos[n]=p; }));

    // 3. Barycentric crossing reduction (3 sweeps)
    function barycentricPass(forward) {
      const layerList = forward
        ? layers.slice(1)
        : layers.slice(0, layers.length-1).reverse();
      layerList.forEach((grp, li) => {
        const refLayer = forward ? li : (layers.length-2-li);
        const bary = {};
        grp.forEach(n => {
          const neighbours = forward ? radj[n] : adj[n];
          const refNeighbours = neighbours.filter(nb => layer[nb] === (forward ? layer[n]-1 : layer[n]+1));
          bary[n] = refNeighbours.length
            ? refNeighbours.reduce((s,nb)=>s+pos[nb],0)/refNeighbours.length
            : pos[n];
        });
        grp.sort((a,b)=>bary[a]-bary[b]);
        grp.forEach((n,p)=>{ pos[n]=p; });
      });
    }
    // More sweeps -> better crossing reduction; cheap enough for our sizes.
    for (let pass = 0; pass < 8; pass++) {
      barycentricPass(pass % 2 === 0);
    }

    // 4. Map (layer, rank) -> pixel coordinates. Stack nodes within each
    //    layer using their ESTIMATED HEIGHT so tall algeq nodes don't
    //    overlap shorter neighbours.
    const result = {};
    layers.forEach((grp, li) => {
      grp.sort((a, b) => pos[a] - pos[b]);
      let y = ORIGIN_Y;
      grp.forEach(n => {
        result[ids[n]] = { x: ORIGIN_X + li * LAYER_W, y };
        y += _estimateHeight(models[n]) + GAP_Y;
      });
    });
    return result;
  }

  // ── Node HTML ──────────────────────────────────────────────────────────────
  // `ins` is an array of per-port input labels; `outs` is the per-port output
  // signal/label array. For algeq, outputs are wrapped in brackets so the
  // [state] form is visually consistent with the input connectors.
  function _html(key, block, outs, ins, title) {
    const defaults = block.inputs || [];
    const insArr = (ins && ins.length) ? ins : defaults;
    const insL = insArr.join(', ');
    const maxOut = Math.max((outs || []).length, (block.outputs || []).length);
    const outLabels = [];
    for (let i = 0; i < maxOut; i++) {
      const v = (outs && outs[i]) || (block.outputs && block.outputs[i]) || '';
      outLabels.push(key === 'algeq' && v ? '[' + v + ']' : v);
    }
    const outL = outLabels.join(', ');
    const hdr  = title || block.label || key;
    return '<div class="node-header">'
      +'<span class="nh-dot" style="background:'+(block.color||'#64748b')+'"></span>'
      +'<span class="nh-title">'+hdr+'</span></div>'
      +'<div class="node-body">'
      +(insL ?'<div class="port-row"><span>'+insL+'</span></div>':'')
      +(outL ?'<div class="port-row" style="justify-content:flex-end"><span>'+outL+'</span></div>':'')
      +'</div>';
  }

  // Ordered, de-duplicated [name] refs extracted from an algeq expression.
  function _algeqStates(expr) {
    const out = [], seen = new Set();
    const re = /\[([a-zA-Z_]\w*)\]/g;
    let m;
    while ((m = re.exec(expr || ''))) {
      if (!seen.has(m[1])) { seen.add(m[1]); out.push(m[1]); }
    }
    return out;
  }

  // Parse args.output_states — accepts either a comma-separated string or
  // an array; also honours the legacy singular `output_state` key. Any state
  // names not present in the expression are still accepted (so the user can
  // type them before editing the expression) but emitted verbatim.
  function _algeqOutputNames(args) {
    args = args || {};
    const raw = args.output_states !== undefined ? args.output_states
              : (args.output_state || '');
    let arr;
    if (Array.isArray(raw)) arr = raw;
    else arr = String(raw).split(',');
    const out = [], seen = new Set();
    arr.forEach(s => {
      const n = (s || '').trim();
      if (n && !seen.has(n)) { seen.add(n); out.push(n); }
    });
    return out;
  }

  // Split an algeq's state refs into inputs/outputs based on its configured
  // output states list. States listed as outputs become output ports (in the
  // order given); the remaining [state] refs from the expression become
  // input ports.
  function _algeqSplit(args) {
    const states = _algeqStates((args||{}).expr);
    const outs   = _algeqOutputNames(args);
    if (!outs.length) return { inputs: states.slice(), outputs: [] };
    const outSet = new Set(outs);
    return {
      inputs:  states.filter(s => !outSet.has(s)),
      outputs: outs.slice(),
    };
  }

  // Per-port input labels.
  //   - For algeq: labels come from the wire's signal_name (bracketed), the
  //     stored input literal (already bracketed by the adapter), or the
  //     signal_name wrapped in brackets if the wire carries a plain name.
  //   - For ramses_out: fallback is the mandatory state name (e.g. "vf").
  //   - For everything else: wire signal_name, else stored literal, else
  //     the catalogue default placeholder.
  function _inputLabels(m, block) {
    if (m.block_type === 'algeq') {
      const wires = Store.get().wires || [];
      const lit   = m.inputs || [];
      return lit.map((v, j) => {
        const w = wires.find(x =>
          x.to_node === m.id && x.to_port === 'input_' + (j + 1));
        if (w && w.signal_name) {
          return /^\[.*\]$/.test(w.signal_name)
            ? w.signal_name
            : '[' + w.signal_name + ']';
        }
        return (typeof v === 'string' && v) ? v : '';
      });
    }
    const defaults = block.inputs || [];
    const wires    = Store.get().wires || [];
    const lit      = m.inputs || [];
    const ramName  = m.block_type === 'ramses_out' && m.args && m.args.name;
    return defaults.map((def, j) => {
      const port = 'input_' + (j + 1);
      const w = wires.find(x => x.to_node === m.id && x.to_port === port);
      if (w && w.signal_name) return w.signal_name;
      const v = lit[j];
      if (typeof v === 'string' && v) return v;
      return ramName || def;
    });
  }

  // Node header title. RAMSES pins show their state name so the user sees
  // "vf" / "omega" on the card instead of the generic catalogue label.
  function _nodeTitle(m, block) {
    if ((m.block_type === 'ramses_in' || m.block_type === 'ramses_out')
        && m.args && m.args.name) {
      return m.args.name;
    }
    return block.label || m.block_type;
  }

  function _refreshNode(sid) {
    const dfId = _s2df(sid); if (dfId === null) return;
    const m = Store.get().models.find(m => m.id === sid); if (!m) return;
    const b = _blocks[m.block_type]; if (!b) return;
    const el = document.querySelector('#node-'+dfId+' .drawflow_content_node');
    if (el) el.innerHTML = _html(m.block_type, b, m.outputs||[],
                                 _inputLabels(m, b), _nodeTitle(m, b));
  }

  const SVG_NS = 'http://www.w3.org/2000/svg';

  // Paint/update the signal-name label at the midpoint of every connection.
  // Drawflow marks each <svg class="connection"> with:
  //   classList[1] = "node_in_node-<dfId>"   (downstream target)
  //   classList[2] = "node_out_node-<dfId>"  (upstream source)
  //   classList[3] = "output_N"
  //   classList[4] = "input_N"
  function _updateWireLabels() {
    const wires = Store.get().wires || [];
    document.querySelectorAll('#drawflow svg.connection').forEach(svg => {
      const cls = svg.classList;
      if (cls.length < 5) return;
      const toDfAttr   = cls[1].replace('node_in_node-',  '');
      const fromDfAttr = cls[2].replace('node_out_node-', '');
      const outPort    = cls[3];
      const inPort     = cls[4];
      const fromDf = parseInt(fromDfAttr, 10);
      const toDf   = parseInt(toDfAttr,   10);
      if (Number.isNaN(fromDf) || Number.isNaN(toDf)) return;
      const fromSid = _df2s(fromDf);
      const toSid   = _df2s(toDf);
      const w = wires.find(x =>
        x.from_node === fromSid && x.to_node === toSid &&
        x.from_port === outPort && x.to_port === inPort);
      const label = (w && w.signal_name) || '';
      let txt = svg.querySelector('text.wire-label');
      if (!label) { if (txt) txt.remove(); return; }
      const path = svg.querySelector('path.main-path') || svg.querySelector('path');
      if (!path) return;
      let pt;
      try { pt = path.getPointAtLength(path.getTotalLength() / 2); }
      catch (e) { return; }
      if (!txt) {
        txt = document.createElementNS(SVG_NS, 'text');
        txt.setAttribute('class', 'wire-label');
        txt.setAttribute('text-anchor', 'middle');
        svg.appendChild(txt);
      }
      txt.textContent = label;
      txt.setAttribute('x', pt.x);
      txt.setAttribute('y', pt.y - 6);
    });
  }

  // ── Create the Drawflow node + DOM + dataset for a block ──────────────────
  // Returns the drawflow id. Does NOT touch the Store; callers handle that.
  // If `ins` is provided it drives both the port count and the labels; this
  // lets algeq have a dynamic connector count derived from its expression.
  function _mount(key, block, x, y, storeId, outs, ins) {
    const nIn  = (ins  !== undefined) ? ins.length  : (block.inputs ||[]).length;
    // For blocks with a dynamic output count (algeq), `outs` length drives
    // the port count — otherwise fall back to the catalogue default.
    const nOut = (outs !== undefined && outs.length !== undefined)
      ? Math.max(outs.length, (block.outputs||[]).length)
      : (block.outputs||[]).length;
    const dfId = _df.addNode(key, nIn, nOut, x, y, key, {store_id:storeId}, _html(key,block,outs,ins));
    const el   = _dfEl(dfId); if(el) el.dataset.storeId = String(storeId);
    return dfId;
  }

  // ── Add a single NEW node (palette drop path) ─────────────────────────────
  function _add(key, block, x, y, sid, eArgs, eOuts) {
    const storeId = String(sid || Store.nextId());
    const nOut = (block.outputs||[]).length;
    const args = Object.assign({}, eArgs||{});
    (block.args||[]).forEach(a=>{ if(!(a.name in args)) args[a.name]=a.default||''; });
    const outs = eOuts ? [...eOuts] : [];
    for(let i=outs.length; i<nOut; i++)
      outs.push(Store.freshSignal(key.replace(/[^a-zA-Z]/g,'').slice(0,3)||'x'));
    // Algeq connectors come from the expression + args.output_state (not
    // blocks.json).
    let ins = undefined;
    let storedInputs = (block.inputs||[]).map(()=>null);
    let finalOuts = outs;
    if (key === 'algeq') {
      const split = _algeqSplit(args);
      ins = split.inputs.map(s => '[' + s + ']');
      storedInputs = ins.slice();
      finalOuts = split.outputs.slice();
    }
    const dfId = _mount(key, block, x, y, storeId, finalOuts, ins);
    Store.addModel({
      id:storeId, df_id:dfId, block_type:key, label:block.label||key,
      color:block.color||'#64748b', args, outputs:finalOuts,
      inputs:storedInputs, pos:{x,y}, comment: ''
    }, false);
    // Repaint so the title / input labels can use args.name for ramses pins.
    _refreshNode(storeId);
    _onChange && _onChange();
    return dfId;
  }

  // ── Drop handler ───────────────────────────────────────────────────────────
  function _onDrop(e) {
    e.preventDefault();
    const raw = e.dataTransfer.getData('text/plain');
    // Palette may encode a pseudo-node as "<key>:<name>" (RAMSES I/O pins).
    let key = raw, nameArg = null;
    const colon = raw.indexOf(':');
    if (colon > 0) { key = raw.slice(0, colon); nameArg = raw.slice(colon + 1); }
    const block = _blocks[key]; if (!block) return;
    const rect  = document.getElementById('drawflow').getBoundingClientRect();
    const zoom  = _df.zoom || 1;
    const x = (e.clientX-rect.left-(_df.canvas_x||0))/zoom;
    const y = (e.clientY-rect.top -(_df.canvas_y||0))/zoom;
    let eArgs = null, eOuts = null;
    if (nameArg) {
      eArgs = { name: nameArg };
      if (key === 'ramses_in')  eOuts = ['['+nameArg+']'];   // bracketed literal
      if (key === 'ramses_out') eOuts = [];                  // no outputs
    }
    _add(key, block, x, y, null, eArgs, eOuts);
  }

  // ── Wire events ───────────────────────────────────────────────────────────
  function _onConn(info) {
    if (_loading) return;
    const fs=_df2s(info.output_id), ts=_df2s(info.input_id); if(!fs||!ts) return;
    const models = Store.get().models;
    const src = models.find(m => m.id === fs);
    const tgt = models.find(m => m.id === ts);
    const idx = parseInt((info.output_class||'output_1').replace('output_',''))-1;
    let sig = (src && src.outputs[idx]) || Store.freshSignal('sig');

    // Target is a RAMSES output pin: rename the upstream output to the
    // mandatory state name so the emitted DSL carries it correctly. Also
    // cascade the rename into any other downstream wires from the same port.
    if (tgt && tgt.block_type === 'ramses_out') {
      const desired = (tgt.args && tgt.args.name) || '';
      if (desired && src && src.outputs[idx] !== desired) {
        const newOuts = [...src.outputs]; newOuts[idx] = desired;
        Store.updateModel(fs, {outputs: newOuts}, false);
        (Store.get().wires||[]).forEach(w => {
          if (w.from_node === fs && w.from_port === info.output_class) {
            w.signal_name = desired;
          }
        });
        sig = desired;
        _refreshNode(fs);
      }
    }
    Store.addWire({from_node:fs,from_port:info.output_class,to_node:ts,to_port:info.input_class,signal_name:sig},false);
    _refreshNode(ts);
    _updateWireLabels();
    _onChange&&_onChange();
  }
  function _onDisc(info) {
    if (_loading) return;
    const fs=_df2s(info.output_id), ts=_df2s(info.input_id); if(!fs||!ts) return;
    Store.removeWire(fs,info.output_class,ts,info.input_class,false);
    _refreshNode(ts);
    _updateWireLabels();
    _onChange&&_onChange();
  }

  // ── Public API ─────────────────────────────────────────────────────────────
  return {
    init(blocksObj, onSelect, onChange) {
      _blocks=blocksObj; _onSelect=onSelect; _onChange=onChange;
      const el=document.getElementById('drawflow');
      _df=new Drawflow(el); _df.reroute=false; _df.curvature=0.45; _df.start();
      el.addEventListener('dragover',e=>e.preventDefault());
      el.addEventListener('drop',_onDrop);
      _df.on('nodeSelected',   id=>{ _selDfId=id; onSelect&&onSelect(_df2s(id)); });
      _df.on('nodeUnselected', ()=>{ _selDfId=null; onSelect&&onSelect(null); });
      _df.on('nodeRemoved',    id=>{
        // Suppressed during loadProject / rebuildNode — the caller manages
        // the Store mutation itself.
        if (_loading) return;
        const m=Store.get().models.find(m=>m.df_id===id);
        if(m) Store.removeModel(m.id,false);
        onSelect&&onSelect(null); onChange&&onChange();
      });
      _df.on('nodeMoved', id=>{
        const sid=_df2s(id); if(!sid) return;
        const d=_df.getNodeFromId(id);
        if(d) Store.updateModel(sid,{pos:{x:d.pos_x,y:d.pos_y}},false);
        _updateWireLabels();
        onChange&&onChange();
      });
      _df.on('connectionCreated',_onConn);
      _df.on('connectionRemoved',_onDisc);
    },

    /**
     * Load a ModelProject onto the canvas.
     * If a block has no pos (e.g. freshly parsed from DSL .txt), run Sugiyama
     * layout first to assign sensible positions.
     */
    loadProject(proj) {
      _loading = true;
      try {
        _df.import({drawflow:{Home:{data:{}}}});

        // Determine whether layout is needed
        const needsLayout = proj.models.length > 0 &&
          proj.models.every(m => !m.pos || (m.pos.x === 0 && m.pos.y === 0));

        const layoutPos = needsLayout ? sugiyamaLayout(proj) : {};

        const idMap={};
        proj.models.forEach(m=>{
          const block=_blocks[m.block_type];
          if(!block){ console.warn('Unknown block:',m.block_type); return; }
          let x, y;
          if (needsLayout && layoutPos[m.id]) {
            x = layoutPos[m.id].x;
            y = layoutPos[m.id].y;
          } else {
            x = (m.pos&&m.pos.x) || 80+Math.random()*400;
            y = (m.pos&&m.pos.y) || 80+Math.random()*300;
          }
          // For algeq the adapter has already decided which states are input
          // ports (in m.inputs) vs output ports (in m.outputs). Use that
          // directly so nIn matches the Store's port layout.
          const ins = (m.block_type === 'algeq')
            ? (m.inputs || []).slice()
            : undefined;
          const dfId = _mount(m.block_type, block, x, y, m.id, m.outputs||[], ins);
          // Existing model is already in the Store (Store.set was called just
          // before this). Just attach the df_id / refresh pos — do NOT push a
          // duplicate model entry.
          Store.updateModel(m.id, {df_id:dfId, pos:{x,y}}, false);
          idMap[m.id]=dfId;
        });

        proj.wires.forEach(w=>{
          const f=idMap[w.from_node],t=idMap[w.to_node]; if(f==null||t==null) return;
          try{ _df.addConnection(f,t,w.from_port||'output_1',w.to_port||'input_1'); }catch(e){}
        });
        // Repaint all nodes so input labels reflect the connected signals.
        proj.models.forEach(m => _refreshNode(m.id));
        _updateWireLabels();
      } finally {
        _loading = false;
      }
    },

    deleteSelected() { if(_selDfId!==null) _df.removeNodeId('node-'+_selDfId); },

    fitView() {
      try {
        const nodes = document.querySelectorAll('#drawflow .drawflow-node');
        const container = _df.container;
        const vw = container.clientWidth;
        const vh = container.clientHeight;
        const applyTransform = (zoom, cx, cy) => {
          _df.zoom = zoom;
          _df.zoom_last_value = zoom;
          _df.canvas_x = cx;
          _df.canvas_y = cy;
          _df.precanvas.style.transform =
            'translate('+cx+'px, '+cy+'px) scale('+zoom+')';
          _df.dispatch('zoom', zoom);
        };
        if (!nodes.length) { applyTransform(1, 0, 0); return; }

        let minX=Infinity, minY=Infinity, maxX=-Infinity, maxY=-Infinity;
        nodes.forEach(el => {
          const x = parseFloat(el.style.left) || 0;
          const y = parseFloat(el.style.top)  || 0;
          const w = el.offsetWidth  || 200;
          const h = el.offsetHeight || 100;
          if (x     < minX) minX = x;
          if (y     < minY) minY = y;
          if (x + w > maxX) maxX = x + w;
          if (y + h > maxY) maxY = y + h;
        });
        const bboxW = Math.max(maxX - minX, 1);
        const bboxH = Math.max(maxY - minY, 1);
        const pad   = 40;

        // Do NOT clamp to _df.zoom_min (default 0.5): fit-to-view must be
        // allowed to shrink further when the diagram is wider than 2x the
        // viewport, otherwise right-side nodes get trimmed. Keep a sane
        // hard floor so text stays legible.
        let zoom = Math.min((vw - 2*pad) / bboxW, (vh - 2*pad) / bboxH, 1);
        zoom = Math.max(zoom, 0.1);

        // Drawflow's precanvas uses transform-origin: 50% 50%, so scaling
        // shrinks/expands around the precanvas centre. To center a given
        // world-point P in the viewport, the translate component must be
        //   t = zoom * (V/2 - P)
        // where V is the viewport dimension (= precanvas layout dimension,
        // which spans 100% of the container).
        const bboxCx = minX + bboxW / 2;
        const bboxCy = minY + bboxH / 2;
        const cx = zoom * (vw / 2 - bboxCx);
        const cy = zoom * (vh / 2 - bboxCy);
        applyTransform(zoom, cx, cy);
      } catch(e) { console.warn('fitView:', e); }
    },

    refreshNode(sid) { _refreshNode(sid); },
    updateWireLabels() { _updateWireLabels(); },

    // Replace the Drawflow node for `sid` with one whose port count matches
    // the Store model's current shape. Wires whose ports still exist are
    // replayed; the rest are dropped from the Store. Intended for algeq
    // after its expression is edited in the inspector.
    rebuildNode(sid) {
      const m = Store.get().models.find(x => x.id === sid); if (!m) return;
      const block = _blocks[m.block_type]; if (!block) return;
      const dfId = _s2df(sid); if (dfId === null) return;
      // For algeq, keep the stored inputs AND outputs in sync with the
      // current expression and args.output_state so port counts and labels
      // match what the inspector shows.
      if (m.block_type === 'algeq') {
        const split = _algeqSplit(m.args);
        Store.updateModel(sid, {
          inputs:  split.inputs.map(s => '[' + s + ']'),
          outputs: split.outputs.slice(),
        }, false);
      }
      const ins = _inputLabels(m, block);
      const nInNew = ins.length;

      // Decide which existing wires can be preserved.
      const wires = (Store.get().wires || []).slice();
      const keep = [], drop = [];
      wires.forEach(w => {
        const survives =
          (w.to_node === sid && (+((w.to_port||'input_0').replace('input_',''))-1) < nInNew) ||
          (w.from_node === sid) ||
          (w.from_node !== sid && w.to_node !== sid);
        (survives ? keep : drop).push(w);
      });

      // Store the new inputs array so future renders see the right slots.
      Store.updateModel(sid, {inputs: ins.slice()}, false);

      _loading = true;
      try {
        _df.removeNodeId('node-' + dfId);
        const x = (m.pos && m.pos.x) || 100;
        const y = (m.pos && m.pos.y) || 100;
        const newDf = _mount(m.block_type, block, x, y, sid, m.outputs||[], ins);
        Store.updateModel(sid, {df_id: newDf}, false);

        // Replay surviving wires connected to this node. Others don't need
        // replay — their SVG wasn't touched because we only removed one node.
        keep
          .filter(w => w.from_node === sid || w.to_node === sid)
          .forEach(w => {
            const f = _s2df(w.from_node), t = _s2df(w.to_node);
            if (f == null || t == null) return;
            try { _df.addConnection(f, t, w.from_port||'output_1', w.to_port||'input_1'); }
            catch (e) {}
          });

        // Prune dropped wires from the Store.
        if (drop.length) {
          const s = Store.get();
          s.wires = keep;
        }
      } finally {
        _loading = false;
      }
      _refreshNode(sid);
      _updateWireLabels();
    },

    getSelectedStoreId() { return _selDfId!==null?_df2s(_selDfId):null; },

    /** Exposed for testing / debugging */
    sugiyamaLayout
  };
})();
