/**
 * main.js
 * App bootstrap + toolbar event handlers + file I/O.
 */

import Store          from './store.js';
import { initSidebar, getCatalogue } from './sidebar.js';
import { initCanvas, rebuildCanvas, clearCanvas, exportDrawflow } from './canvas.js';
import { initForms, selectBlock }   from './forms.js';
import { initDslPreview, getDslText, getLastDsl } from './dsl_preview.js';
import * as Api       from './api.js';

async function main() {
  const catRes = await Api.getBlocks();
  if (catRes.ok) window._cgCatalogue = catRes.data;

  await initSidebar((blockType, def) => { /* drag-start hook */ });
  initCanvas(blockId => { selectBlock(blockId); });
  initForms();
  initDslPreview();

  /* ---- Toolbar ---------------------------------------------------------- */
  document.getElementById('btn-new').addEventListener('click', () => {
    if (!confirm('Start a new model? Unsaved changes will be lost.')) return;
    Store.reset();
    clearCanvas();
  });

  document.getElementById('btn-load-txt').addEventListener('click', () => {
    document.getElementById('file-txt').click();
  });

  document.getElementById('btn-load-proj').addEventListener('click', () => {
    document.getElementById('file-proj').click();
  });

  document.getElementById('btn-save-dsl').addEventListener('click', async () => {
    const { dsl, error } = await getDslText();
    if (error) { alert('Cannot save DSL: ' + error); return; }
    const p = Store.getProject();
    _download(dsl, (p.modelName || 'model') + '.txt', 'text/plain');
  });

  document.getElementById('btn-save-proj').addEventListener('click', () => {
    const p = Store.getProject();
    p.canvas.drawflow = exportDrawflow();
    const proj = { format: 'cgproj-v1', savedAt: new Date().toISOString(), project: p };
    _download(JSON.stringify(proj, null, 2), (p.modelName||'model') + '.cgproj', 'application/json');
  });

  document.getElementById('btn-run-codegen').addEventListener('click', async () => {
    const btn = document.getElementById('btn-run-codegen');
    btn.textContent = '⏳ Running…';
    btn.disabled = true;
    try {
      const { dsl, error: dslErr } = await getDslText();
      if (dslErr) { alert('DSL error: ' + dslErr); return; }
      const p = Store.getProject();
      const res = await Api.runCodegen(dsl, p.modelType, p.modelName);
      if (!res.ok) { alert('Server error: ' + res.error); return; }
      const d = res.data;
      if (d.success) {
        _download(d.f90_text, d.f90_filename, 'text/plain');
        _showToast('✅ ' + d.f90_filename + ' downloaded');
      } else {
        alert('codegen failed (return code ' + d.returncode + '):\n\n' + (d.stderr || d.stdout || '(no output)'));
      }
    } finally {
      btn.textContent = '▶ Run Codegen';
      btn.disabled = false;
    }
  });

  /* ---- File inputs ------------------------------------------------------ */
  document.getElementById('file-txt').addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    const text = await file.text();
    const res = await Api.parseDsl(text);
    if (!res.ok) { alert('Parse error: ' + res.error); return; }
    const project = res.data;
    if (project.errors && project.errors.length)
      console.warn('Parse warnings:', project.errors);
    clearCanvas();
    Store.setProject(project);
    rebuildCanvas(project);
    _showToast('Loaded: ' + file.name);
    e.target.value = '';
  });

  document.getElementById('file-proj').addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const json = JSON.parse(await file.text());
      if (!json.project) throw new Error('Invalid .cgproj format');
      clearCanvas();
      Store.setProject(json.project);
      rebuildCanvas(json.project);
      _showToast('Loaded: ' + file.name);
    } catch (err) {
      alert('Failed to load project: ' + err.message);
    }
    e.target.value = '';
  });
}

function _download(text, filename, mime) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: mime }));
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function _showToast(msg) {
  let t = document.getElementById('cgs-toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'cgs-toast';
    t.style.cssText = 'position:fixed;bottom:24px;right:24px;background:#1e293b;color:#e2e8f0;' +
      'padding:10px 18px;border-radius:8px;border:1px solid #334155;font-size:13px;z-index:9999;' +
      'box-shadow:0 4px 12px rgba(0,0,0,.4);transition:opacity .3s';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.style.opacity = '1';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.style.opacity = '0'; }, 3000);
}

main().catch(console.error);
