/**
 * canvas.js — Drawflow canvas: node CRUD, drag-drop, wiring, sync to Store
 *
 * Phase 3 additions:
 *   - sugiyamaLayout(proj) — assigns (x,y) positions when importing a DSL .txt
 *     that has no canvas metadata. Uses longest-path layering + barycentric
 *     crossing-reduction (two-pass, three iterations).
 */
window.Canvas = (() => {
  let _df, _blocks={}, _onSelect, _onChange, _selDfId=null;

  const LAYER_W = 260;  // horizontal spacing between layers (px)
  const LAYER_H = 130;  // vertical spacing within a layer (px)
  const ORIGIN_X = 80;
  const ORIGIN_Y = 80;

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
    for (let pass=0; pass<3; pass++) {
      barycentricPass(pass%2===0);
    }

    // 4. Map to pixel coordinates
    const result = {};
    ids.forEach((id,i) => {
      result[id] = {
        x: ORIGIN_X + layer[i] * LAYER_W,
        y: ORIGIN_Y + pos[i]  * LAYER_H
      };
    });
    return result;
  }

  // ── Node HTML ──────────────────────────────────────────────────────────────
  function _html(key, block, outs) {
    const ins  = (block.inputs||[]).join(', ');
    const outL = (block.outputs||[]).map((o,i)=>outs[i]||o).join(', ');
    return '<div class="node-header">'
      +'<span class="nh-dot" style="background:'+(block.color||'#64748b')+'"></span>'
      +'<span class="nh-title">'+(block.label||key)+'</span></div>'
      +'<div class="node-body">'
      +(ins  ?'<div class="port-row"><span>'+ins+'</span></div>':'')
      +(outL ?'<div class="port-row" style="justify-content:flex-end"><span>'+outL+'</span></div>':'')
      +'</div>';
  }

  // ── Add a single node ──────────────────────────────────────────────────────
  function _add(key, block, x, y, sid, eArgs, eOuts) {
    const storeId = sid || Store.nextId();
    const nIn  = (block.inputs||[]).length;
    const nOut = (block.outputs||[]).length;
    const args = Object.assign({}, eArgs||{});
    (block.args||[]).forEach(a=>{ if(!(a.name in args)) args[a.name]=a.default||''; });
    const outs = eOuts ? [...eOuts] : [];
    for(let i=outs.length; i<nOut; i++)
      outs.push(Store.freshSignal(key.replace(/[^a-zA-Z]/g,'').slice(0,3)||'x'));
    const dfId = _df.addNode(key, nIn, nOut, x, y, key, {store_id:storeId}, _html(key,block,outs));
    const el   = _dfEl(dfId); if(el) el.dataset.storeId = storeId;
    Store.addModel({
      id:storeId, df_id:dfId, block_type:key, label:block.label||key,
      color:block.color||'#64748b', args, outputs:outs,
      inputs:(block.inputs||[]).map(()=>null), pos:{x,y}
    }, false);
    _onChange && _onChange();
    return dfId;
  }

  // ── Drop handler ───────────────────────────────────────────────────────────
  function _onDrop(e) {
    e.preventDefault();
    const key=e.dataTransfer.getData('text/plain'), block=_blocks[key]; if(!block) return;
    const rect=document.getElementById('drawflow').getBoundingClientRect();
    const zoom=_df.zoom||1;
    _add(key, block,
      (e.clientX-rect.left-(_df.canvas_x||0))/zoom,
      (e.clientY-rect.top -(_df.canvas_y||0))/zoom);
  }

  // ── Wire events ───────────────────────────────────────────────────────────
  function _onConn(info) {
    const fs=_df2s(info.output_id), ts=_df2s(info.input_id); if(!fs||!ts) return;
    const m=Store.get().models.find(m=>m.id===fs);
    const idx=parseInt((info.output_class||'output_1').replace('output_',''))-1;
    const sig=(m&&m.outputs[idx])||Store.freshSignal('sig');
    Store.addWire({from_node:fs,from_port:info.output_class,to_node:ts,to_port:info.input_class,signal_name:sig},false);
    _onChange&&_onChange();
  }
  function _onDisc(info) {
    const fs=_df2s(info.output_id), ts=_df2s(info.input_id); if(!fs||!ts) return;
    Store.removeWire(fs,info.output_class,ts,info.input_class,false);
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
        const m=Store.get().models.find(m=>m.df_id===id);
        if(m) Store.removeModel(m.id,false);
        onSelect&&onSelect(null); onChange&&onChange();
      });
      _df.on('nodeMoved', id=>{
        const sid=_df2s(id); if(!sid) return;
        const d=_df.getNodeFromId(id);
        if(d) Store.updateModel(sid,{pos:{x:d.pos_x,y:d.pos_y}},false);
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
        idMap[m.id]=_add(m.block_type,block,x,y,m.id,m.args,m.outputs);
      });

      proj.wires.forEach(w=>{
        const f=idMap[w.from_node],t=idMap[w.to_node]; if(!f||!t) return;
        try{ _df.addConnection(f,t,w.from_port||'output_1',w.to_port||'input_1'); }catch(e){}
      });
    },

    deleteSelected() { if(_selDfId!==null) _df.removeNodeId('node-'+_selDfId); },
    fitView()        { try{_df.zoom_reset();}catch(e){} },

    refreshNode(sid) {
      const dfId=_s2df(sid); if(dfId===null) return;
      const m=Store.get().models.find(m=>m.id===sid); if(!m) return;
      const b=_blocks[m.block_type]; if(!b) return;
      const el=document.querySelector('#node-'+dfId+' .drawflow_content_node');
      if(el) el.innerHTML=_html(m.block_type,b,m.outputs||[]);
    },

    getSelectedStoreId() { return _selDfId!==null?_df2s(_selDfId):null; },

    /** Exposed for testing / debugging */
    sugiyamaLayout
  };
})();
