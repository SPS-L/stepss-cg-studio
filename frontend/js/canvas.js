/**
 * canvas.js — Drawflow canvas: node CRUD, drag-drop, wiring, sync to Store
 */
window.Canvas = (() => {
  let _df, _blocks={}, _onSelect, _onChange, _selDfId=null;

  const _dfEl    = id  => document.querySelector('#node-'+id);
  const _df2s    = id  => { const el=_dfEl(id); return el?el.dataset.storeId:null; };
  const _s2df    = sid => { const el=document.querySelector('.drawflow-node[data-store-id="'+sid+'"]');
                            return el?parseInt(el.id.replace('node-','')):null; };

  function _html(key, block, outs) {
    const ins  = (block.inputs||[]).join(', ');
    const outL = (block.outputs||[]).map((o,i)=>outs[i]||o).join(', ');
    return '<div class="node-header"><span class="nh-dot" style="background:'+(block.color||'#64748b')+'"></span>'
      +'<span class="nh-title">'+(block.label||key)+'</span></div>'
      +'<div class="node-body">'
      +(ins  ?'<div class="port-row"><span>'+ins+'</span></div>':'')
      +(outL ?'<div class="port-row" style="justify-content:flex-end"><span>'+outL+'</span></div>':'')
      +'</div>';
  }

  function _add(key, block, x, y, sid, eArgs, eOuts) {
    const storeId = sid || Store.nextId();
    const nIn  = (block.inputs||[]).length;
    const nOut = (block.outputs||[]).length;
    const args = Object.assign({}, eArgs||{});
    (block.args||[]).forEach(a=>{ if(!(a.name in args)) args[a.name]=a.default||''; });
    const outs = eOuts ? [...eOuts] : [];
    for(let i=outs.length; i<nOut; i++) outs.push(Store.freshSignal(key.replace(/[^a-zA-Z]/g,'').slice(0,3)||'x'));
    const dfId = _df.addNode(key, nIn, nOut, x, y, key, {store_id:storeId}, _html(key,block,outs));
    const el   = _dfEl(dfId); if(el) el.dataset.storeId = storeId;
    Store.addModel({id:storeId,df_id:dfId,block_type:key,label:block.label||key,
      color:block.color||'#64748b',args,outputs:outs,
      inputs:(block.inputs||[]).map(()=>null),pos:{x,y}}, false);
    _onChange && _onChange();
    return dfId;
  }

  function _onDrop(e) {
    e.preventDefault();
    const key=e.dataTransfer.getData('text/plain'), block=_blocks[key]; if(!block) return;
    const rect=document.getElementById('drawflow').getBoundingClientRect();
    const zoom=_df.zoom||1;
    _add(key, block,
      (e.clientX-rect.left-(_df.canvas_x||0))/zoom,
      (e.clientY-rect.top -(_df.canvas_y||0))/zoom);
  }

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
    loadProject(proj) {
      _df.import({drawflow:{Home:{data:{}}}});
      const idMap={};
      proj.models.forEach(m=>{
        const block=_blocks[m.block_type]; if(!block){console.warn('Unknown block:',m.block_type);return;}
        idMap[m.id]=_add(m.block_type,block,(m.pos&&m.pos.x)||80+Math.random()*500,
          (m.pos&&m.pos.y)||80+Math.random()*300,m.id,m.args,m.outputs);
      });
      proj.wires.forEach(w=>{
        const f=idMap[w.from_node],t=idMap[w.to_node]; if(!f||!t) return;
        try{_df.addConnection(f,t,w.from_port||'output_1',w.to_port||'input_1');}catch(e){}
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
    getSelectedStoreId() { return _selDfId!==null?_df2s(_selDfId):null; }
  };
})();
