/**
 * api.js — fetch wrappers for the FastAPI backend at same origin
 */
window.Api = (() => {
  async function _post(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({detail: r.statusText}));
      throw new Error(e.detail || r.statusText);
    }
    return r.json();
  }
  async function _get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  }
  return {
    getBlocks()          { return _get('/blocks'); },
    parseDSL(dsl_text)   { return _post('/parse', {dsl_text}); },
    async emitDSL(proj)  { const {dsl_text} = await _post('/emit', {project: proj}); return dsl_text; },
    runCodegen(dsl_text, model_type, model_name) {
      return _post('/run_codegen', {dsl_text, model_type, model_name}); },
    getConfig()          { return _get('/config'); },
    updateConfig(cfg)    { return fetch('/config', {method:'PUT',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(cfg)}).then(r=>r.json()); }
  };
})();
