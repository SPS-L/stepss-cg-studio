/**
 * dsl_preview.js — debounced live DSL preview with syntax highlighting
 */
window.DslPreview = (() => {
  let _timer=null, _last='';
  const EL = () => document.getElementById('dsl-preview-content');

  function _hl(txt) {
    return txt
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/(^%\w+)/gm,'<span class="dsl-section">$1</span>')
      .replace(/(![^\n]*)/g,'<span class="dsl-comment">$1</span>')
      .replace(/\b(-?\d+\.?\d*([eE][+-]?\d+)?)\b/g,'<span class="dsl-number">$1</span>')
      .replace(/\{([^}]+)\}/g,'<span class="dsl-string">{$1}</span>')
      .replace(/\[([^\]]+)\]/g,'<span class="dsl-keyword">[$1]</span>');
  }

  async function _render() {
    try {
      const dsl = await Api.emitDSL(Store.get());
      _last = dsl; EL().innerHTML = _hl(dsl);
    } catch(e) {
      EL().innerHTML = '<span class="dsl-comment">! ' + String(e.message||'emit error').replace(/</g,'&lt;') + '</span>';
    }
  }

  return {
    init() {
      document.getElementById('btn-copy-dsl').addEventListener('click', () => {
        if (!_last) return;
        navigator.clipboard.writeText(_last).then(()=>Toast.show('DSL copied','success'));
      });
    },
    schedule()       { clearTimeout(_timer); _timer=setTimeout(_render,600); },
    async renderNow(){ clearTimeout(_timer); await _render(); },
    getLast()        { return _last; }
  };
})();
