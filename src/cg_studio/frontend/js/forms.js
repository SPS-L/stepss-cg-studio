/**
 * forms.js — metadata section tables + node inspector
 */
window.Forms = (() => {
  const SPECS = {
    data:        [{k:'name',pl:'KA'},{k:'value',pl:'200.0'},{k:'comment',pl:'optional'}],
    parameters:  [{k:'name',pl:'VREF'},{k:'expr',pl:'vcomp(...)+...'},{k:'comment',pl:''}],
    states:      [{k:'name',pl:'Vf'},{k:'init',pl:'0.0'},{k:'comment',pl:''}],
    observables: [{k:'name',pl:'Vt'},{k:'expr',pl:'[Vf]*{KA}'},{k:'comment',pl:''}]
  };
  let _onChange = null;

  function _buildSection(sec) {
    const spec = SPECS[sec];
    const rows = Store.get()[sec] || [];
    const pane = document.getElementById('tab-' + sec);
    pane.innerHTML = '';
    const tbl    = document.createElement('table'); tbl.className = 'meta-table';
    const thead  = document.createElement('thead');
    const hr     = document.createElement('tr');
    spec.forEach(c => { const th = document.createElement('th'); th.textContent = c.k.charAt(0).toUpperCase()+c.k.slice(1); hr.appendChild(th); });
    const thd = document.createElement('th'); thd.style.width='24px'; hr.appendChild(thd);
    thead.appendChild(hr); tbl.appendChild(thead);
    const tbody = document.createElement('tbody');
    rows.forEach((row, i) => tbody.appendChild(_row(sec, i, row, spec)));
    tbl.appendChild(tbody); pane.appendChild(tbl);
    const addBtn = document.createElement('button');
    addBtn.className = 'meta-add-row'; addBtn.textContent = '+ Add row';
    addBtn.addEventListener('click', () => {
      const empty = {}; spec.forEach(c => empty[c.k] = '');
      Store.addRow(sec, empty); _buildSection(sec); _onChange && _onChange();
    });
    pane.appendChild(addBtn);
  }

  function _row(sec, i, row, spec) {
    const tr = document.createElement('tr');
    spec.forEach(c => {
      const td = document.createElement('td');
      const inp = document.createElement('input');
      inp.className = 'meta-input'; inp.type = 'text';
      inp.value = row[c.k]||''; inp.placeholder = c.pl;
      inp.addEventListener('change', e => { Store.updateRow(sec,i,{[c.k]:e.target.value}); _onChange&&_onChange(); });
      td.appendChild(inp); tr.appendChild(td);
    });
    const tdDel = document.createElement('td');
    const btn   = document.createElement('button');
    btn.className='row-del'; btn.textContent='\u00D7'; btn.title='Remove';
    btn.addEventListener('click', () => { Store.removeRow(sec,i); _buildSection(sec); _onChange&&_onChange(); });
    tdDel.appendChild(btn); tr.appendChild(tdDel); return tr;
  }

  function _initTabs() {
    document.querySelectorAll('.meta-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.meta-tab').forEach(b=>b.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-'+btn.dataset.tab).classList.add('active');
      });
    });
  }

  function showInspector(storeId) {
    const titleEl = document.getElementById('inspector-title');
    const formEl  = document.getElementById('inspector-form');
    formEl.innerHTML = '';
    if (!storeId) { titleEl.textContent = 'Select a block to inspect'; return; }
    const model = Store.get().models.find(m => m.id === storeId); if (!model) return;
    const block = Palette.getBlock(model.block_type);
    titleEl.textContent = (block&&block.label) || model.block_type;
    // Output signal name fields
    ((block&&block.outputs)||[]).forEach((outKey, idx) => {
      const f = _field('Output \"' + outKey + '\" signal', model.outputs[idx]||'');
      f.querySelector('input').addEventListener('change', e => {
        const newSig = e.target.value;
        const o = [...(model.outputs||[])]; o[idx] = newSig;
        Store.updateModel(storeId,{outputs:o});
        // Cascade: any outgoing wire on this output port now carries the new
        // signal name, and downstream nodes must repaint to show it.
        const port = 'output_' + (idx + 1);
        const downstream = new Set();
        (Store.get().wires||[]).forEach(w => {
          if (w.from_node === storeId && w.from_port === port) {
            w.signal_name = newSig;
            downstream.add(w.to_node);
          }
        });
        Canvas.refreshNode(storeId);
        downstream.forEach(sid => Canvas.refreshNode(sid));
        Canvas.updateWireLabels();
        _onChange&&_onChange();
      });
      formEl.appendChild(f);
    });
    // Args — algeq is handled below with its own tailored fields (single
    // Expression field + Output state selector), so skip the generic loop.
    if (model.block_type !== 'algeq') {
      ((block&&block.args)||[]).forEach(a => {
        const val = (model.args&&model.args[a.name]!==undefined) ? model.args[a.name] : (a.default||'');
        const f   = _field(a.name + (a.description?' — '+a.description:''), val);
        f.querySelector('input').addEventListener('change', e => {
          Store.updateModel(storeId,{args:Object.assign({},model.args||{},{[a.name]:e.target.value})});
          _onChange&&_onChange();
        });
        formEl.appendChild(f);
      });
    }
    if (model.block_type==='algeq') {
      // Single Expression field — updates Store AND rebuilds the Drawflow
      // node so the port count / labels follow the new [state] refs.
      const exprF = _field('Expression', (model.args&&model.args.expr)||'');
      exprF.querySelector('input').addEventListener('change', e => {
        Store.updateModel(storeId,{args:Object.assign({},model.args||{},{expr:e.target.value})});
        Canvas.rebuildNode(storeId);
        _onChange&&_onChange();
      });
      formEl.appendChild(exprF);

      // Optional output states. Comma-separated list; each name becomes an
      // output connector. Blank => no output pins and every [state] in the
      // expression stays on an input pin.
      const currentOuts =
        (model.args && (Array.isArray(model.args.output_states)
                          ? model.args.output_states.join(', ')
                          : (model.args.output_states || model.args.output_state || '')))
        || '';
      const outF = _field(
        'Output states (comma-separated, leave blank if none)',
        currentOuts
      );
      outF.querySelector('input').addEventListener('change', e => {
        const list = e.target.value
          .split(',')
          .map(s => s.trim())
          .filter(Boolean);
        const newArgs = Object.assign({}, model.args||{}, {output_states: list});
        // Drop the legacy singular key so no two sources of truth exist.
        delete newArgs.output_state;
        Store.updateModel(storeId, {
          args: newArgs,
          outputs: list.slice(),
        });
        Canvas.rebuildNode(storeId);
        _onChange && _onChange();
      });
      formEl.appendChild(outF);
    }

    // Comment — appears on every block, saved inside the project (.cgproj)
    // and written onto the DSL header line (& blockname  ! comment) on emit.
    const cmtF = _field('Comment', model.comment || '');
    cmtF.querySelector('input').addEventListener('change', e => {
      Store.updateModel(storeId, {comment: e.target.value});
      _onChange && _onChange();
    });
    formEl.appendChild(cmtF);
  }

  function _field(label, value) {
    const wrap = document.createElement('div'); wrap.className = 'insp-field';
    const lbl  = document.createElement('label'); lbl.textContent = label;
    const inp  = document.createElement('input'); inp.type='text'; inp.value=value;
    wrap.append(lbl, inp); return wrap;
  }

  return {
    init(onChange) { _onChange=onChange; _initTabs(); this.refresh(); },
    refresh() { ['data','parameters','states','observables'].forEach(_buildSection); },
    showInspector
  };
})();
