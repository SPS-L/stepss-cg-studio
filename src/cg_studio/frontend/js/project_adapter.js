/**
 * project_adapter.js — backend parser shape ↔ frontend Store shape.
 *
 * The /parse endpoint returns the canonical backend ModelProject (camelCase
 * keys, flat `blocks[]` with inline `inputStates`/`outputState`, observables
 * as strings, states with `initExpr`). The Canvas/Store/Forms modules expect
 * snake_case keys, separate `models[]` + `wires[]`, observables as objects,
 * and states with an `init` field.
 *
 * `parsedToFrontend` rebuilds that shape:
 *   - wires are synthesized between producers and consumers of each state;
 *   - `algeq` blocks have dynamic connectors derived from the [state] refs
 *     in their expression. A state referenced by an algeq with no explicit
 *     producer but with consumers elsewhere is promoted: the algeq gets an
 *     **output port** for that state and wires it to those consumers;
 *   - unresolved signals (RAMSES inputs like [omega], parameter refs like
 *     {KE}, or state references with no producing block) are preserved as
 *     literal strings in `models[i].inputs[j]` so the emit round-trip keeps
 *     them (the backend `_normalise_project` in app.py honours these);
 *   - when `opts.ramsesInputs` / `opts.ramsesOutputs` are provided the
 *     adapter also auto-seeds ramses_in / ramses_out pseudo-nodes for each
 *     RAMSES I/O actually used and wires them up.
 *
 * Exposed on window so it can be shared between main.js and Node-based unit
 * tests.
 */
(function () {
  // Ordered, de-duplicated list of [name] refs from an algeq expression.
  function algeqStateRefs(expr) {
    const out = [], seen = new Set();
    const re = /\[([a-zA-Z_]\w*)\]/g;
    let m;
    while ((m = re.exec(expr || ''))) {
      if (!seen.has(m[1])) { seen.add(m[1]); out.push(m[1]); }
    }
    return out;
  }

  function parsedToFrontend(parsed, blocks, opts) {
    parsed = parsed || {};
    blocks = blocks || {};
    opts   = opts   || {};
    const parsedBlocks = parsed.blocks || [];
    const mt           = parsed.modelType || 'exc';
    const ramInSet     = new Set((opts.ramsesInputs  || {})[mt] || []);
    const ramOutSet    = new Set((opts.ramsesOutputs || {})[mt] || []);
    // Full set of RAMSES-reserved names for this model type (superset of
    // palette inputs; e.g. adds `if` for exc). An algeq must never promote
    // one of these to its output even if it has consumers — they are
    // provided by the RAMSES runtime. Mandatory outputs are excluded so
    // they can still be promoted when an algeq defines them.
    const ramReservedRaw = new Set((opts.ramsesReserved || {})[mt] || []);
    ramOutSet.forEach(n => ramReservedRaw.delete(n));
    const ramReservedSet = ramReservedRaw;
    // Unified "don't promote" set used by the classifier below.
    const noPromoteSet = new Set([...ramInSet, ...ramReservedSet]);

    // -- Pass 1: producers from non-algeq blocks ----------------------------
    // producerIndex[state] = { id, port }   — port is 0-based output-port index.
    const producerIndex = {};
    parsedBlocks.forEach(b => {
      if (b.blockType === 'algeq') return;
      if (b.outputState && !(b.outputState in producerIndex)) {
        producerIndex[b.outputState] = { id: String(b.id), port: 0 };
      }
    });

    // -- Pass 2: determine which states each algeq "owns" as output. --------
    // A state referenced by an algeq gets promoted to that algeq's output if
    // it has no other producer and at least one consumer elsewhere. Consumers
    // are any non-algeq block that reads the state as input, or any other
    // algeq that references the state in its expression.
    const nonAlgeqInputUsage = new Set();
    parsedBlocks.forEach(b => {
      if (b.blockType === 'algeq') return;
      (b.inputStates || []).forEach(s => { if (s) nonAlgeqInputUsage.add(s); });
    });
    const algeqRefs = new Map();  // b.id -> [state, ...]
    parsedBlocks.forEach(b => {
      if (b.blockType !== 'algeq') return;
      algeqRefs.set(b.id, algeqStateRefs((b.args || {}).expr));
    });

    // Pick AT MOST ONE output state per algeq, then classify the remaining
    // refs as inputs.
    //   Priority for the output state:
    //     1. a ref that is a mandatory RAMSES output (vf/tm/ix/iy/...)
    //     2. the first ref that has no other producer and has a consumer
    //   If neither applies, the algeq has no output state — all refs stay
    //   on input ports.
    //
    // DONE IN TWO PHASES so that late promotions (e.g. algeq #9 promoted as
    // producer of [Id]) are visible to EARLIER algeqs that reference the
    // same state — otherwise those earlier algeqs would keep the literal
    // "[Id]" on their port instead of being wired to the producer.
    //   Phase (a): iterate algeqs in order, pick outState, extend
    //              producerIndex.
    //   Phase (b): iterate algeqs again, classify inputs using the now
    //              complete producerIndex.
    // algeqInfo[bid] = {
    //   inPorts:  [{state, producer?}, ...],
    //   outState: '' | 'name',
    // }
    // Pre-compute how many OTHER blocks/algeqs reference each state. Used
    // as a tie-breaker when auto-picking an algeq's output: a state that
    // appears in fewer other places is more likely to be locally defined
    // by this algeq (e.g. [mur] in HVDC_LCC's mu equation), whereas a state
    // referenced everywhere (e.g. [alpha]) is probably defined elsewhere.
    const refCountByState = new Map();
    const bumpRef = s => refCountByState.set(s, (refCountByState.get(s) || 0) + 1);
    parsedBlocks.forEach(b => {
      if (b.blockType === 'algeq') {
        (algeqRefs.get(b.id) || []).forEach(bumpRef);
      } else {
        (b.inputStates || []).forEach(s => { if (s) bumpRef(s); });
      }
    });

    // Helper for the auto-pick: which algeq (if any) should own this state?
    const algeqInfo = {};
    const pickOutputsFor = (b) => {
      const bid    = String(b.id);
      const states = algeqRefs.get(b.id) || [];
      // Honour explicit user choice — accept either the new `output_states`
      // (array / comma-separated) or the legacy `output_state` (singular).
      const userRaw = (b.args || {}).output_states !== undefined
        ? (b.args || {}).output_states
        : ((b.args || {}).output_state || '');
      const userList = (Array.isArray(userRaw) ? userRaw
                        : String(userRaw).split(','))
        .map(s => (s || '').trim()).filter(Boolean);
      if (userList.length) return userList.filter(s => states.includes(s));

      // Auto-pick at most ONE state.
      //   1. mandatory RAMSES outputs (unproduced).
      //   2. otherwise the eligible state referenced in the FEWEST other
      //      places — that's the one the algeq most plausibly defines.
      const mand = states.find(s => ramOutSet.has(s) && !producerIndex[s]);
      if (mand) return [mand];

      const eligible = states.filter(s => {
        if (noPromoteSet.has(s)) return false;
        if (producerIndex[s] && producerIndex[s].id !== bid) return false;
        const consumedByOtherAlgeq = parsedBlocks.some(o =>
          o.blockType === 'algeq' && String(o.id) !== bid &&
          (algeqRefs.get(o.id) || []).includes(s));
        return nonAlgeqInputUsage.has(s) || consumedByOtherAlgeq;
      });
      if (!eligible.length) return [];
      eligible.sort((a, b) => {
        const ca = (refCountByState.get(a) || 0);
        const cb = (refCountByState.get(b) || 0);
        if (ca !== cb) return ca - cb;          // fewer refs win
        return states.indexOf(a) - states.indexOf(b);  // stable on source order
      });
      return [eligible[0]];
    };

    parsedBlocks.forEach(b => {
      if (b.blockType !== 'algeq') return;
      const bid    = String(b.id);
      const states = algeqRefs.get(b.id) || [];
      const picks  = pickOutputsFor(b);
      picks.forEach((s, i) => { producerIndex[s] = { id: bid, port: i }; });
      algeqInfo[bid] = { outStates: picks, _states: states };
    });

    // Phase (b): classify inputs for each algeq.
    parsedBlocks.forEach(b => {
      if (b.blockType !== 'algeq') return;
      const bid    = String(b.id);
      const info   = algeqInfo[bid];
      const outSet = new Set(info.outStates);
      const inPorts = [];
      info._states.forEach(s => {
        if (outSet.has(s)) return;
        if (noPromoteSet.has(s)) {
          inPorts.push({ state: s, producer: null });
          return;
        }
        const prod = producerIndex[s];
        if (prod && prod.id !== bid) {
          inPorts.push({ state: s, producer: prod });
        } else {
          inPorts.push({ state: s, producer: null });
        }
      });
      info.inPorts = inPorts;
      delete info._states;
    });

    // -- Pass 3: build models[] and wires[] ---------------------------------
    const models = [], wires = [];
    parsedBlocks.forEach(b => {
      const def = blocks[b.blockType] || {};
      const bid = String(b.id);
      const isAlgeq = b.blockType === 'algeq';

      if (isAlgeq) {
        const info = algeqInfo[bid] || { inPorts: [], outStates: [] };
        const ins = [];
        info.inPorts.forEach((ent, j) => {
          if (ent.producer) {
            wires.push({
              from_node: ent.producer.id,
              from_port: 'output_' + (ent.producer.port + 1),
              to_node:   bid,
              to_port:   'input_' + (j + 1),
              signal_name: ent.state,
            });
            ins.push(null);
          } else {
            // RAMSES input or orphan — show the literal on the port.
            ins.push('[' + ent.state + ']');
          }
        });
        // Record the inferred output list on args so the inspector's
        // "Output states" field reflects it and round-trips via .cgproj.
        const outArgs = Object.assign({}, b.args || {});
        outArgs.output_states = info.outStates.slice();
        delete outArgs.output_state;  // drop legacy singular key
        models.push({
          id: bid, df_id: null, block_type: 'algeq',
          label: def.label || 'algeq', color: def.color || '#6b7280',
          args: outArgs,
          outputs: info.outStates.slice(),
          inputs: ins,
          pos: { x: 0, y: 0 }, rawArgLines: b.rawArgLines || [],
          comment: b.comment || ''
        });
        return;
      }

      const nIn  = (def.inputs  || []).length;
      const nOut = (def.outputs || []).length;
      const outs = [];
      if (nOut > 0) outs.push(b.outputState || '');
      while (outs.length < nOut) outs.push('');
      const ins = [];
      for (let j = 0; j < nIn; j++) {
        const sig = (b.inputStates && b.inputStates[j]) || '';
        const prod = producerIndex[sig];
        if (sig && prod && prod.id !== bid) {
          wires.push({
            from_node: prod.id, from_port: 'output_' + (prod.port + 1),
            to_node:   bid,     to_port:   'input_' + (j + 1),
            signal_name: sig,
          });
          ins.push(null);
        } else {
          ins.push(sig || null);
        }
      }
      models.push({
        id: bid, df_id: null, block_type: b.blockType,
        label: def.label || b.blockType, color: def.color || '#64748b',
        args: b.args || {}, outputs: outs, inputs: ins,
        pos: { x: 0, y: 0 }, rawArgLines: b.rawArgLines || [],
        comment: b.comment || ''
      });
    });

    // -- Pass 4: auto-seed RAMSES I/O pseudo-nodes and wire them up. --------
    const ramIn   = (opts.ramsesInputs  || {})[mt] || [];
    const ramOut  = (opts.ramsesOutputs || {})[mt] || [];
    let pseudoSeq = 0;
    const nextPid = () => 'io_' + (++pseudoSeq);
    const inBlock  = blocks['ramses_in']  || {};
    const outBlock = blocks['ramses_out'] || {};

    ramIn.forEach((name, i) => {
      const literal = '[' + name + ']';
      const consumers = [];
      models.forEach(m => {
        (m.inputs || []).forEach((v, j) => {
          if (v === literal) consumers.push({ model: m, port: j });
        });
      });
      if (!consumers.length) return;
      const pid = nextPid();
      models.push({
        id: pid, df_id: null, block_type: 'ramses_in',
        label: inBlock.label || 'RAMSES Input',
        color: inBlock.color || '#06b6d4',
        args: { name }, outputs: [literal], inputs: [],
        // Leave pos={0,0} so Canvas.loadProject runs Sugiyama and places the
        // pseudo-pin alongside the real blocks on the left (sources).
        pos: { x: 0, y: 0 }
      });
      consumers.forEach(c => {
        wires.push({
          from_node: pid, from_port: 'output_1',
          to_node:   c.model.id, to_port: 'input_' + (c.port + 1),
          signal_name: literal,
        });
        c.model.inputs[c.port] = null;
      });
    });

    ramOut.forEach((name, i) => {
      const producers = models.filter(m =>
        m.block_type !== 'ramses_in' && m.block_type !== 'ramses_out' &&
        (m.outputs || []).includes(name));
      if (!producers.length) return;
      const pid = nextPid();
      models.push({
        id: pid, df_id: null, block_type: 'ramses_out',
        label: outBlock.label || 'RAMSES Output',
        color: outBlock.color || '#f59e0b',
        args: { name }, outputs: [], inputs: [null],
        // Leave pos={0,0} so Sugiyama places the sink at the rightmost layer.
        pos: { x: 0, y: 0 }
      });
      producers.forEach(p => {
        const idx = (p.outputs || []).indexOf(name);
        wires.push({
          from_node: p.id, from_port: 'output_' + (idx + 1),
          to_node:   pid,  to_port:   'input_1',
          signal_name: name,
        });
      });
    });

    return {
      model_type: parsed.modelType || 'exc',
      model_name: parsed.modelName || 'my_model',
      data: parsed.data || [],
      parameters: parsed.parameters || [],
      states: (parsed.states || []).map(s => ({
        name: s.name,
        init: s.initExpr !== undefined ? s.initExpr : (s.init || ''),
        comment: s.comment || ''
      })),
      observables: (parsed.observables || []).map(o =>
        typeof o === 'string' ? { name: o, expr: '', comment: '' } : o
      ),
      models: models, wires: wires, canvas_meta: {}
    };
  }

  const api = { parsedToFrontend: parsedToFrontend };
  if (typeof window !== 'undefined') window.ProjectAdapter = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
