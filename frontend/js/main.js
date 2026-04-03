/**
 * main.js — app bootstrap, toolbar, keyboard shortcuts, file I/O
 */
window.Toast = {
  show(msg, type='', dur=3000) {
    const el=document.createElement('div');
    el.className='toast'+(type?' '+type:''); el.textContent=msg;
    document.getElementById('toast-container').appendChild(el);
    setTimeout(()=>el.remove(), dur);
  }
};
window.Modal = {
  show(title, bodyHtml, okLabel='OK', cancelLabel='') {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML    = bodyHtml;
    document.getElementById('modal-ok').textContent   = okLabel;
    const cb = document.getElementById('modal-cancel');
    cb.textContent=cancelLabel; cb.style.display=cancelLabel?'':'none';
    document.getElementById('modal-overlay').classList.remove('hidden');
    return new Promise(res => {
      document.getElementById('modal-ok').onclick     = ()=>{ this.hide(); res(true); };
      document.getElementById('modal-cancel').onclick = ()=>{ this.hide(); res(false); };
    });
  },
  hide() { document.getElementById('modal-overlay').classList.add('hidden'); }
};

(async function main() {
  let blocks={};
  try { blocks=await Api.getBlocks(); }
  catch(e) { Toast.show('Backend unreachable: '+e.message,'error',8000); }

  Palette.init(blocks);
  Forms.init(onChange);
  Canvas.init(blocks, onSelect, onChange);
  DslPreview.init();
  _syncHeader();
  DslPreview.schedule();

  // Model type + name
  document.getElementById('sel-model-type').addEventListener('change', e=>{
    Store.patch({model_type:e.target.value}); onChange(); });
  document.getElementById('inp-model-name').addEventListener('change', e=>{
    const n=e.target.value.trim().replace(/\s+/g,'_')||'my_model';
    e.target.value=n; Store.patch({model_name:n});
    document.getElementById('model-title').textContent=n; onChange(); });

  // Undo/Redo
  document.getElementById('btn-undo').addEventListener('click',()=>{
    if(Store.undo()){_reload();Forms.refresh();onChange();} });
  document.getElementById('btn-redo').addEventListener('click',()=>{
    if(Store.redo()){_reload();Forms.refresh();onChange();} });
  document.getElementById('btn-del').addEventListener('click',()=>Canvas.deleteSelected());
  document.getElementById('btn-fit').addEventListener('click',()=>Canvas.fitView());

  // New
  document.getElementById('btn-new').addEventListener('click', async ()=>{
    const ok=await Modal.show('New Model','Discard current model?','Discard','Cancel');
    if(!ok) return;
    Store.reset(); _reload(); Forms.refresh(); _syncHeader(); onChange(); });

  // Load DSL
  document.getElementById('btn-load-dsl').addEventListener('click',()=>
    document.getElementById('file-input-dsl').click());
  document.getElementById('file-input-dsl').addEventListener('change', async e=>{
    const f=e.target.files[0]; if(!f) return; e.target.value='';
    try {
      const proj=await Api.parseDSL(await f.text());
      Store.set(proj); _reload(); Forms.refresh(); _syncHeader(); onChange();
      Toast.show('Loaded: '+proj.model_name,'success');
    } catch(err){ Toast.show('Parse error: '+err.message,'error'); } });

  // Load Project
  document.getElementById('btn-load-project').addEventListener('click',()=>
    document.getElementById('file-input-project').click());
  document.getElementById('file-input-project').addEventListener('change', async e=>{
    const f=e.target.files[0]; if(!f) return; e.target.value='';
    try {
      const proj=JSON.parse(await f.text());
      Store.set(proj); _reload(); Forms.refresh(); _syncHeader(); onChange();
      Toast.show('Project loaded: '+proj.model_name,'success');
    } catch(err){ Toast.show('Load error: '+err.message,'error'); } });

  // Save Project
  document.getElementById('btn-save').addEventListener('click',()=>{
    const p=Store.get();
    _dl(new Blob([JSON.stringify(p,null,2)],{type:'application/json'}),(p.model_name||'model')+'.json');
    Toast.show('Project saved','success'); });

  // Export DSL
  document.getElementById('btn-export-dsl').addEventListener('click', async ()=>{
    await DslPreview.renderNow();
    const dsl=DslPreview.getLast();
    if(!dsl){Toast.show('Nothing to export','error');return;}
    _dl(new Blob([dsl],{type:'text/plain'}),(Store.get().model_name||'model')+'.txt');
    Toast.show('DSL exported','success'); });

  // Run Codegen
  document.getElementById('btn-codegen').addEventListener('click', async ()=>{
    await DslPreview.renderNow();
    const dsl=DslPreview.getLast();
    if(!dsl){Toast.show('Generate DSL first','error');return;}
    const p=Store.get(); Toast.show('Running codegen\u2026');
    try {
      const res=await Api.runCodegen(dsl,p.model_type,p.model_name);
      if(res.error){
        await Modal.show('Codegen Error','<pre>'+_esc(res.error)+'</pre>','Close');
      } else {
        const f90=res.f90_text||res.output||'';
        const confirmed=await Modal.show(
          'Success \u2014 '+p.model_name+'.f90',
          '<pre>'+_esc(f90.slice(0,8000))+(f90.length>8000?'\n\u2026':'')+'</pre>',
          'Download .f90','Close');
        if(confirmed&&f90) _dl(new Blob([f90],{type:'text/plain'}),(p.model_name||'model')+'.f90');
      }
    } catch(err){ Toast.show('Codegen failed: '+err.message,'error'); } });

  // Keyboard
  document.addEventListener('keydown', e=>{
    const tag=document.activeElement.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA') return;
    if(e.key==='Delete'||e.key==='Backspace') Canvas.deleteSelected();
    if((e.ctrlKey||e.metaKey)&&e.key==='z'){e.preventDefault();
      if(Store.undo()){_reload();Forms.refresh();onChange();}}
    if((e.ctrlKey||e.metaKey)&&(e.key==='y'||(e.shiftKey&&e.key==='Z'))){
      e.preventDefault(); if(Store.redo()){_reload();Forms.refresh();onChange();}}
    if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();
      document.getElementById('btn-save').click();}
  });

  function onSelect(sid) { Forms.showInspector(sid); _status(); }
  function onChange()    { DslPreview.schedule(); _undoRedo(); _status(); }
  function _reload()     { Canvas.loadProject(Store.get()); }
  function _syncHeader() {
    const p=Store.get();
    document.getElementById('sel-model-type').value=p.model_type||'exc';
    document.getElementById('inp-model-name').value=p.model_name||'my_model';
    document.getElementById('model-title').textContent=p.model_name||'Untitled model';
  }
  function _undoRedo() {
    document.getElementById('btn-undo').disabled=!Store.canUndo();
    document.getElementById('btn-redo').disabled=!Store.canRedo();
  }
  function _status() {
    const p=Store.get(), sorted=Store.topoSort();
    document.getElementById('canvas-status').innerHTML = !sorted
      ? '<span style="color:var(--danger)">&#9888; Cycle detected</span>'
      : p.models.length+' blocks, '+p.wires.length+' wires';
  }
  function _dl(blob,name){
    const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name;
    a.click(); URL.revokeObjectURL(a.href);
  }
  function _esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  _undoRedo(); _status();
})();
