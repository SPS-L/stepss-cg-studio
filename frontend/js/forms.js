/**
 * forms.js
 * Right-panel tabbed forms:
 *   - Model tab (type, name, observables)
 *   - Data tab (%data table)
 *   - Params tab (%parameters table)
 *   - States tab (%states table)
 *   - Block/Props tab (selected block args)
 */

import Store from './store.js';

let _selectedBlockId = null;

export function initForms() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
  });

  document.addEventListener('store:change', () => {
    renderModelTab();
    renderDataTab();
    renderParamsTab();
    renderStatesTab();
    if (_selectedBlockId !== null) renderBlockTab(_selectedBlockId);
  });

  renderModelTab();
  renderDataTab();
  renderParamsTab();
  renderStatesTab();
}

export function selectBlock(blockId) {
  _selectedBlockId = blockId;
  renderBlockTab(blockId);
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  const btn = document.querySelector('.tab-btn[data-tab="props"]');
  if (btn) btn.classList.add('active');
  const pane = document.getElementById('tab-props');
  if (pane) pane.classList.add('active');
}

/* ---- Model tab ---------------------------------------------------------- */
function renderModelTab() {
  const p = Store.getProject();
  const pane = document.getElementById('tab-model');
  if (!pane) return;
  pane.innerHTML = `
    <label class="form-label">Model Type</label>
    <select id="f-model-type" class="form-select">
      ${['exc','tor','inj','twop'].map(t =>
        `<option value="${t}" ${p.modelType===t?'selected':''}>${t.toUpperCase()}</option>`
      ).join('')}
    </select>
    <label class="form-label" style="margin-top:10px">Model Name</label>
    <input id="f-model-name" class="form-input" value="${_esc(p.modelName)}" />
    <label class="form-label" style="margin-top:10px">Observables <span style="font-weight:400;font-size:11px">(one per line)</span></label>
    <textarea id="f-observables" class="form-textarea" rows="4">${p.observables.join('\n')}</textarea>
    <button id="f-model-save" class="btn btn-primary" style="margin-top:8px;width:100%">Apply</button>
  `;
  pane.querySelector('#f-model-save').addEventListener('click', () => {
    const type = pane.querySelector('#f-model-type').value;
    const name = pane.querySelector('#f-model-name').value.trim() || 'MyModel';
    const obs  = pane.querySelector('#f-observables').value
                     .split('\n').map(s=>s.trim()).filter(Boolean);
    Store.setModelMeta(type, name);
    Store.setObservables(obs);
  });
}

/* ---- Data tab ----------------------------------------------------------- */
function renderDataTab() {
  const p = Store.getProject();
  const pane = document.getElementById('tab-data');
  if (!pane) return;
  pane.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <span style="font-size:12px;color:var(--text-dim)">%data parameters</span>
      <button id="f-data-add" class="btn" style="padding:3px 10px;font-size:12px">+ Add</button>
    </div>
    <table class="form-table">
      <thead><tr><th>Name</th><th>Comment</th><th></th></tr></thead>
      <tbody id="f-data-body">
        ${p.data.map((d,i) => `
          <tr>
            <td><input class="form-input" data-idx="${i}" data-field="name"    value="${_esc(d.name)}"    /></td>
            <td><input class="form-input" data-idx="${i}" data-field="comment" value="${_esc(d.comment)}" /></td>
            <td><button class="btn-icon del-row" data-idx="${i}">✕</button></td>
          </tr>`).join('')}
      </tbody>
    </table>
  `;
  _bindTableEvents(pane, 'data', () => Store.getProject().data, Store.setData);
}

/* ---- Params tab --------------------------------------------------------- */
function renderParamsTab() {
  const p = Store.getProject();
  const pane = document.getElementById('tab-params');
  if (!pane) return;
  pane.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <span style="font-size:12px;color:var(--text-dim)">%parameters</span>
      <button id="f-params-add" class="btn" style="padding:3px 10px;font-size:12px">+ Add</button>
    </div>
    <table class="form-table">
      <thead><tr><th>Name</th><th>Expression</th><th>&amp;</th><th></th></tr></thead>
      <tbody id="f-params-body">
        ${p.parameters.map((d,i) => `
          <tr>
            <td><input class="form-input" data-idx="${i}" data-field="name" value="${_esc(d.name)}" /></td>
            <td><input class="form-input" data-idx="${i}" data-field="expr" value="${_esc(d.expr)}" /></td>
            <td><input type="checkbox" data-idx="${i}" data-field="continuation" ${d.continuation?'checked':''}></td>
            <td><button class="btn-icon del-row" data-idx="${i}">✕</button></td>
          </tr>`).join('')}
      </tbody>
    </table>
  `;
  _bindTableEvents(pane, 'params', () => Store.getProject().parameters, Store.setParameters);
}

/* ---- States tab --------------------------------------------------------- */
function renderStatesTab() {
  const p = Store.getProject();
  const pane = document.getElementById('tab-states');
  if (!pane) return;
  pane.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <span style="font-size:12px;color:var(--text-dim)">%states (init values)</span>
      <button id="f-states-add" class="btn" style="padding:3px 10px;font-size:12px">+ Add</button>
    </div>
    <table class="form-table">
      <thead><tr><th>Name</th><th>Init expr</th><th>Comment</th><th></th></tr></thead>
      <tbody id="f-states-body">
        ${p.states.map((d,i) => `
          <tr>
            <td><input class="form-input" data-idx="${i}" data-field="name"     value="${_esc(d.name)}" /></td>
            <td><input class="form-input" data-idx="${i}" data-field="initExpr" value="${_esc(d.initExpr)}" /></td>
            <td><input class="form-input" data-idx="${i}" data-field="comment"  value="${_esc(d.comment)}" /></td>
            <td><button class="btn-icon del-row" data-idx="${i}">✕</button></td>
          </tr>`).join('')}
      </tbody>
    </table>
  `;
  _bindTableEvents(pane, 'states', () => Store.getProject().states, Store.setStates);
}

/* ---- Block / Props tab -------------------------------------------------- */
function renderBlockTab(blockId) {
  const pane = document.getElementById('tab-props');
  if (!pane) return;
  if (blockId === null) {
    pane.innerHTML = '<p style="color:var(--text-dim);font-size:12px;padding:8px">Click a block on the canvas to edit its properties.</p>';
    return;
  }
  const p = Store.getProject();
  const block = p.blocks.find(b => b.id === blockId);
  if (!block) { pane.innerHTML = '<p style="color:var(--error);font-size:12px;padding:8px">Block not found.</p>'; return; }

  const cat = window._cgCatalogue || {};
  const def = cat[block.blockType] || { label: block.blockType, args: [], inputs: [], outputs: [] };

  const inputRows = (block.inputStates || []).map((sig, i) => `
    <tr>
      <td style="color:var(--text-dim)">Input ${i+1}</td>
      <td><input class="form-input" id="bp-input-${i}" value="${_esc(sig)}" /></td>
    </tr>`).join('');

  const argRows = (def.args || []).map(a => `
    <tr>
      <td style="color:var(--text-dim)">${_esc(a.label||a.name)}</td>
      <td><input class="form-input" id="bp-arg-${a.name}" value="${_esc(block.args[a.name]||a.default||'')}" /></td>
    </tr>`).join('');

  pane.innerHTML = `
    <div style="font-size:13px;font-weight:700;margin-bottom:8px">${_esc(def.label||block.blockType)}</div>
    <div style="font-size:11px;color:var(--text-dim);margin-bottom:12px">${_esc(def.description||'')}</div>
    <table class="form-table">
      <tbody>
        <tr>
          <td style="color:var(--text-dim)">Output state</td>
          <td><input class="form-input" id="bp-output" value="${_esc(block.outputState)}" /></td>
        </tr>
        ${inputRows}
        ${argRows}
        <tr>
          <td style="color:var(--text-dim)">Comment</td>
          <td><input class="form-input" id="bp-comment" value="${_esc(block.comment||'')}" /></td>
        </tr>
      </tbody>
    </table>
    <button id="bp-apply" class="btn btn-primary" style="margin-top:10px;width:100%">Apply</button>
    <button id="bp-delete" class="btn" style="margin-top:6px;width:100%;background:var(--error);border-color:var(--error)">Delete Block</button>
  `;

  pane.querySelector('#bp-apply').addEventListener('click', () => {
    const patch = {
      outputState: pane.querySelector('#bp-output').value.trim(),
      comment: pane.querySelector('#bp-comment').value.trim(),
      args: {},
      inputStates: (block.inputStates||[]).map((_,i) => {
        const el = pane.querySelector(`#bp-input-${i}`);
        return el ? el.value.trim() : '';
      }),
    };
    (def.args||[]).forEach(a => {
      const el = pane.querySelector(`#bp-arg-${a.name}`);
      if (el) patch.args[a.name] = el.value.trim();
    });
    Store.updateBlock(blockId, patch);
  });

  pane.querySelector('#bp-delete').addEventListener('click', () => {
    Store.removeBlock(blockId);
    _selectedBlockId = null;
    renderBlockTab(null);
  });
}

/* ---- Helpers ------------------------------------------------------------ */
function _esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function _bindTableEvents(pane, prefix, getArr, setArr) {
  const addBtn = pane.querySelector(`#f-${prefix}-add`);
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      const arr = [...getArr()];
      if (prefix === 'data')   arr.push({ name: '', comment: '' });
      if (prefix === 'params') arr.push({ name: '', expr: '', continuation: false });
      if (prefix === 'states') arr.push({ name: '', initExpr: '0.', comment: '' });
      setArr(arr);
    });
  }

  pane.querySelectorAll('.del-row').forEach(btn => {
    btn.addEventListener('click', () => {
      const arr = [...getArr()];
      arr.splice(parseInt(btn.dataset.idx), 1);
      setArr(arr);
    });
  });

  pane.querySelectorAll('input[data-field]').forEach(input => {
    input.addEventListener('change', () => {
      const arr = [...getArr()];
      const idx = parseInt(input.dataset.idx);
      const field = input.dataset.field;
      const val = input.type === 'checkbox' ? input.checked : input.value;
      if (arr[idx]) arr[idx] = { ...arr[idx], [field]: val };
      setArr(arr);
    });
  });
}
