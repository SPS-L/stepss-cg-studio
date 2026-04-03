/**
 * api.js
 * fetch() wrappers for all backend endpoints.
 * All functions return { ok: bool, data: any, error: string|null }.
 */

const BASE = '';  // same origin

async function _call(method, path, body) {
  try {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const r = await fetch(BASE + path, opts);
    const json = await r.json().catch(() => ({}));
    if (!r.ok) return { ok: false, data: null, error: json.detail || r.statusText };
    return { ok: true, data: json, error: null };
  } catch (e) {
    return { ok: false, data: null, error: e.message };
  }
}

export async function getBlocks()   { return _call('GET', '/blocks'); }
export async function getConfig()   { return _call('GET', '/config'); }
export async function putConfig(c)  { return _call('PUT', '/config', c); }

export async function parseDsl(dslText) {
  return _call('POST', '/parse', { dsl_text: dslText });
}

export async function emitDsl(project) {
  return _call('POST', '/emit', { project });
}

export async function runCodegen(dslText, modelType, modelName) {
  return _call('POST', '/run_codegen', {
    dsl_text: dslText,
    model_type: modelType || '',
    model_name: modelName || '',
  });
}
