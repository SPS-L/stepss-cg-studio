/**
 * validate.js — structural checks on a ModelProject.
 *
 * findFloatingStateIssues(proj):
 *   Returns a list of issues of the form
 *       { state, model_id, port, peers: [other_model_id, ...] }
 *   for every input slot that carries a state literal (no wire attached)
 *   whose state name is also referenced by at least one OTHER block —
 *   those two places should be connected by a wire.
 *
 *   Rationale: a CODEGEN DSL state is a single scalar, so multiple blocks
 *   that reference the same state must all be wired to the block that
 *   produces it. A "floating" literal therefore indicates either a missing
 *   wire in the canvas or a lingering literal that never got promoted into
 *   a connection during load.
 */
(function () {
  // Strip brackets from a signal/literal so "[omega]" / "omega" compare equal.
  function _stateName(label) {
    if (!label || typeof label !== 'string') return '';
    const m = /^\[([a-zA-Z_]\w*)\]$/.exec(label.trim());
    return m ? m[1] : label.trim();
  }

  function findFloatingStateIssues(proj) {
    const models = (proj && proj.models) || [];
    const wires  = (proj && proj.wires)  || [];

    // name -> [{model_id, role, port}], role ∈ {output, input_literal, input_wired, algeq_expr}
    const refs = new Map();
    const pushRef = (name, entry) => {
      if (!name) return;
      if (!refs.has(name)) refs.set(name, []);
      refs.get(name).push(entry);
    };

    models.forEach(m => {
      // Outputs
      (m.outputs || []).forEach((s, i) => {
        if (s) pushRef(_stateName(s), {model_id: m.id, role: 'output', port: i});
      });
      // Stored input literals (no wire attached)
      (m.inputs || []).forEach((v, j) => {
        if (typeof v === 'string' && v) {
          pushRef(_stateName(v), {model_id: m.id, role: 'input_literal', port: j});
        }
      });
    });
    // Wires contribute the upstream signal for every consumer.
    wires.forEach(w => {
      if (w.signal_name) {
        pushRef(_stateName(w.signal_name), {model_id: w.to_node, role: 'input_wired'});
      }
    });

    const issues = [];
    refs.forEach((entries, name) => {
      const floats = entries.filter(e => e.role === 'input_literal');
      if (!floats.length) return;
      // Any peer entry on a DIFFERENT model (output, wired input, or another
      // floating literal somewhere else) means this literal should have been
      // a wire.
      floats.forEach(f => {
        const peers = [...new Set(
          entries
            .filter(e => e !== f && e.model_id !== f.model_id)
            .map(e => e.model_id)
        )];
        if (peers.length > 0) {
          issues.push({
            state: name,
            model_id: f.model_id,
            port: f.port,
            peers,
          });
        }
      });
    });
    return issues;
  }

  // Group issues by state for terser user-facing output.
  function summariseIssues(issues) {
    const byState = new Map();
    issues.forEach(x => {
      if (!byState.has(x.state)) byState.set(x.state, new Set());
      byState.get(x.state).add(x.model_id);
      x.peers.forEach(p => byState.get(x.state).add(p));
    });
    return [...byState.entries()]
      .map(([state, ids]) => ({state, models: [...ids]}))
      .sort((a, b) => a.state.localeCompare(b.state));
  }

  const api = { findFloatingStateIssues, summariseIssues };
  if (typeof window !== 'undefined') window.Validate = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
