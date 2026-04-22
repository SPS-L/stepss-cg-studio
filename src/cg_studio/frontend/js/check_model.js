/**
 * check_model.js — structural validator that runs from the Check Model
 * button. Returns a list of issues {level, category, message, block_id?}
 * so the caller can render them in the Issues panel.
 *
 * Categories checked:
 *   - mandatory_output     — missing mandatory RAMSES output for the model type
 *   - ramses_input         — required RAMSES input pins not present / not wired
 *   - disconnected_input   — a block input slot has neither a wire nor a literal
 *   - ramses_output_disc   — a ramses_out pin has no incoming wire
 *   - floating_state       — state literal on one block, same state used elsewhere (reuses Validate)
 *   - undeclared_param     — {name} used but not in %data or %parameters
 *   - undeclared_state     — [name]/plain state used but not produced and not declared
 *   - param_no_init        — %parameters entry with empty expression
 *   - state_no_init        — %states entry with empty initializer
 */
(function () {
  function _label(m) {
    const t = m.block_type || '?';
    if (t === 'ramses_in' || t === 'ramses_out') {
      return t + '(' + ((m.args || {}).name || '?') + ')';
    }
    return t + ' #' + m.id;
  }

  function _collectRefs(text, params, states) {
    if (typeof text !== 'string') return;
    const reP = /\{([a-zA-Z_]\w*)\}/g;
    const reS = /\[([a-zA-Z_]\w*)\]/g;
    let m;
    while ((m = reP.exec(text))) params.add(m[1]);
    while ((m = reS.exec(text))) states.add(m[1]);
  }

  // Required RAMSES inputs per model type for the "minimum inputs" check.
  //   If `names` is set, those specific RAMSES inputs MUST all be present.
  //   Otherwise `min` is the minimum count of connected ramses_in pins.
  const _REQUIRED_INPUTS = {
    exc:  { min: 1, names: null },
    tor:  { min: 1, names: null },
    inj:  { min: 2, names: ['vx', 'vy'] },
    twop: { min: 4, names: ['vx1', 'vy1', 'vx2', 'vy2'] },
  };

  function run(proj, opts) {
    proj = proj || {};
    opts = opts || {};
    const mt        = proj.model_type || 'exc';
    const ramIn     = (opts.ramsesInputs  || {})[mt] || [];
    const ramOut    = (opts.ramsesOutputs || {})[mt] || [];
    const models    = proj.models || [];
    const wires     = proj.wires  || [];
    const issues    = [];

    const ramInSet  = new Set(ramIn);
    const ramOutSet = new Set(ramOut);

    const wiresInto = new Map();  // model_id -> Set of ports
    const wiresFrom = new Map();  // model_id -> count
    wires.forEach(w => {
      if (!wiresInto.has(w.to_node)) wiresInto.set(w.to_node, new Set());
      wiresInto.get(w.to_node).add(w.to_port);
      wiresFrom.set(w.from_node, (wiresFrom.get(w.from_node) || 0) + 1);
    });

    // -- 1. Mandatory outputs ------------------------------------------------
    const producedNames = new Set();
    models.forEach(m => (m.outputs || []).forEach(o => producedNames.add(o)));
    ramOut.forEach(name => {
      if (!producedNames.has(name)) {
        issues.push({
          level: 'error', category: 'mandatory_output',
          message: 'Missing mandatory output state \u2018' + name +
                   '\u2019 for model type \u2018' + mt + '\u2019.',
        });
      } else {
        // Also verify the ramses_out pin for this name is wired.
        const pin = models.find(m =>
          m.block_type === 'ramses_out' && (m.args || {}).name === name);
        if (pin && !(wiresInto.get(pin.id) || new Set()).size) {
          issues.push({
            level: 'error', category: 'ramses_output_disc',
            message: 'RAMSES output pin \u2018' + name +
                     '\u2019 is on the canvas but not connected to any block.',
            block_id: pin.id,
          });
        }
      }
    });

    // -- 2. Minimum RAMSES inputs -------------------------------------------
    const req = _REQUIRED_INPUTS[mt];
    if (req) {
      const connected = new Set();
      models.forEach(m => {
        if (m.block_type !== 'ramses_in') return;
        if ((wiresFrom.get(m.id) || 0) > 0) connected.add((m.args || {}).name || '');
      });
      if (req.names) {
        req.names.forEach(name => {
          if (!connected.has(name)) {
            issues.push({
              level: 'error', category: 'ramses_input',
              message: 'RAMSES input \u2018[' + name +
                       ']\u2019 is required for model type \u2018' + mt +
                       '\u2019 but is missing or not connected.',
            });
          }
        });
      } else if (connected.size < req.min) {
        issues.push({
          level: 'error', category: 'ramses_input',
          message: 'Model type \u2018' + mt + '\u2019 needs at least ' +
                   req.min + ' connected RAMSES input pin(s); found ' +
                   connected.size + '.',
        });
      }
    }

    // -- 3. Disconnected inputs on regular blocks ---------------------------
    models.forEach(m => {
      if (m.block_type === 'ramses_in' || m.block_type === 'ramses_out') return;
      (m.inputs || []).forEach((v, j) => {
        const port = 'input_' + (j + 1);
        const wired = (wiresInto.get(m.id) || new Set()).has(port);
        const hasLit = typeof v === 'string' && v.trim().length > 0;
        if (!wired && !hasLit) {
          issues.push({
            level: 'warning', category: 'disconnected_input',
            message: 'Block ' + _label(m) + ' has a disconnected input on port ' + (j + 1) + '.',
            block_id: m.id,
          });
        }
      });
    });

    // -- 4. Floating state references (delegates to Validate) ---------------
    if (typeof Validate !== 'undefined' && Validate.findFloatingStateIssues) {
      const floats = Validate.findFloatingStateIssues(proj);
      const groups = Validate.summariseIssues(floats);
      groups.forEach(g => {
        issues.push({
          level: 'warning', category: 'floating_state',
          message: 'State \u2018' + g.state +
                   '\u2019 is referenced by ' + g.models.length +
                   ' blocks but some of the connectors are not wired.',
        });
      });
    }

    // -- 5. Undeclared parameters and states --------------------------------
    const declaredData   = new Set((proj.data || []).map(d => (d.name || '').trim()).filter(Boolean));
    const declaredParams = new Set((proj.parameters || []).map(p => (p.name || '').trim()).filter(Boolean));
    const declaredStates = new Set((proj.states || []).map(s => (s.name || '').trim()).filter(Boolean));

    const paramRefs = new Set(), stateRefs = new Set();
    models.forEach(m => {
      Object.values(m.args || {}).forEach(v => _collectRefs(v, paramRefs, stateRefs));
      (m.inputs || []).forEach(v => _collectRefs(v, paramRefs, stateRefs));
    });
    (proj.parameters  || []).forEach(p => _collectRefs(p.expr || '', paramRefs, stateRefs));
    (proj.states      || []).forEach(s => _collectRefs(s.init || '', paramRefs, stateRefs));
    (proj.observables || []).forEach(o => _collectRefs(o.expr || '', paramRefs, stateRefs));

    // Sort for stable output.
    [...paramRefs].sort().forEach(name => {
      if (declaredData.has(name) || declaredParams.has(name)) return;
      issues.push({
        level: 'error', category: 'undeclared_param',
        message: 'Parameter \u2018{' + name +
                 '}\u2019 is referenced but not declared in %data or %parameters.',
      });
    });

    const blockOutputs = new Set();
    models.forEach(m => (m.outputs || []).forEach(o => o && blockOutputs.add(o)));
    [...stateRefs].sort().forEach(name => {
      if (blockOutputs.has(name))   return;
      if (ramInSet.has(name))       return;
      if (ramOutSet.has(name))      return;
      if (declaredStates.has(name)) return;
      issues.push({
        level: 'error', category: 'undeclared_state',
        message: 'State \u2018[' + name +
                 ']\u2019 is referenced but is not produced by any block, ' +
                 'not a RAMSES I/O, and not declared in %states.',
      });
    });

    // Plain (unbracketed) state refs on non-algeq block input slots.
    const flagged = new Set();
    models.forEach(m => {
      if (m.block_type === 'algeq' ||
          m.block_type === 'ramses_in' ||
          m.block_type === 'ramses_out') return;
      (m.inputs || []).forEach((v, j) => {
        if (typeof v !== 'string') return;
        const s = v.trim(); if (!s) return;
        if (/^\{.*\}$/.test(s))      return;  // parameter ref — param check catches it
        if (/^[-+\d.]/.test(s))      return;  // numeric literal
        const bm = /^\[([a-zA-Z_]\w*)\]$/.exec(s);
        const name = bm ? bm[1] : s;
        if (blockOutputs.has(name))   return;
        if (ramInSet.has(name))       return;
        if (ramOutSet.has(name))      return;
        if (declaredStates.has(name)) return;
        const key = m.id + '|' + j;
        if (flagged.has(key)) return;
        flagged.add(key);
        issues.push({
          level: 'error', category: 'undeclared_state',
          message: 'State \u2018' + s + '\u2019 used on ' + _label(m) +
                   ' input port ' + (j + 1) + ' but not declared.',
          block_id: m.id,
        });
      });
    });

    // -- 6. Parameters not initialised --------------------------------------
    (proj.parameters || []).forEach(p => {
      if (!(p.name || '').trim()) return;
      if (!(p.expr || '').toString().trim()) {
        issues.push({
          level: 'error', category: 'param_no_init',
          message: 'Parameter \u2018' + p.name + '\u2019 has no initialiser expression.',
        });
      }
    });

    // -- 7. States not initialised ------------------------------------------
    (proj.states || []).forEach(s => {
      if (!(s.name || '').trim()) return;
      if (!(s.init || '').toString().trim()) {
        issues.push({
          level: 'warning', category: 'state_no_init',
          message: 'State \u2018' + s.name + '\u2019 has no initialiser; ' +
                   'CODEGEN will pick a default, but an explicit value is safer.',
        });
      }
    });

    return issues;
  }

  // ── Renderer (browser-only; Node tests only use run()) ─────────────────
  function render(issues) {
    const wrap   = document.getElementById('issues-wrap');
    const titleEl= document.getElementById('issues-title');
    const listEl = document.getElementById('issues-list');
    if (!wrap || !titleEl || !listEl) return;
    listEl.innerHTML = '';
    wrap.classList.remove('has-errors', 'has-warnings', 'no-issues');
    wrap.classList.remove('collapsed');  // always expand on a fresh run

    if (!issues.length) {
      titleEl.textContent = '\u2713 No issues';
      wrap.classList.add('no-issues');
      const ok = document.createElement('div');
      ok.className = 'issue-none';
      ok.textContent = 'No issues found.';
      listEl.appendChild(ok);
      return;
    }
    const errs  = issues.filter(x => x.level === 'error').length;
    const warns = issues.filter(x => x.level === 'warning').length;
    titleEl.textContent = 'Issues (' + errs + ' errors, ' + warns + ' warnings)';
    if (errs)  wrap.classList.add('has-errors');
    else       wrap.classList.add('has-warnings');

    issues.forEach(iss => {
      const row = document.createElement('div');
      row.className = 'issue-row issue-' + iss.level;
      const lvl = document.createElement('span');
      lvl.className = 'issue-level';
      lvl.textContent = iss.level === 'error' ? 'ERROR' : 'WARN';
      const msg = document.createElement('span');
      msg.className = 'issue-msg';
      msg.textContent = iss.message;
      row.append(lvl, msg);
      if (iss.block_id) {
        row.style.cursor = 'pointer';
        row.title = 'Click to inspect block';
        row.addEventListener('click', () => {
          if (typeof Forms !== 'undefined' && Forms.showInspector) {
            Forms.showInspector(iss.block_id);
          }
        });
      }
      listEl.appendChild(row);
    });
  }

  const api = { run, render };
  if (typeof window !== 'undefined') window.CheckModel = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
