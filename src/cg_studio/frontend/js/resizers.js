/**
 * resizers.js — click-and-drag resize for the right panel (inspector + DSL
 * preview) and the bottom meta panel (%data / %parameters / ...).
 *
 * The splitter divs are #split-right (vertical bar, horizontal drag) and
 * #split-meta (horizontal bar, vertical drag). Sizes are persisted in
 * localStorage so they survive reloads.
 */
window.Resizers = (() => {
  const RIGHT_MIN = 180, RIGHT_MAX = 900;
  const META_MIN  = 60,  META_MAX  = 700;
  const KEY_RIGHT = 'cg_right_width_px';
  const KEY_META  = 'cg_meta_height_px';

  function _clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function _restore(sel, dim, min, max, key) {
    const el = document.querySelector(sel); if (!el) return;
    const saved = parseInt(localStorage.getItem(key) || '', 10);
    if (Number.isFinite(saved)) el.style[dim] = _clamp(saved, min, max) + 'px';
  }

  function _wire(splitSel, panelSel, dim, opts) {
    const splitter = document.querySelector(splitSel);
    const panel    = document.querySelector(panelSel);
    if (!splitter || !panel) return;
    splitter.addEventListener('mousedown', e => {
      e.preventDefault();
      const axisClient = dim === 'width' ? 'clientX' : 'clientY';
      const start      = e[axisClient];
      const startSize  = dim === 'width' ? panel.offsetWidth : panel.offsetHeight;
      // Both panels live AFTER their splitter in document order, so dragging
      // the splitter towards the panel (right for #right-panel, down for
      // #meta-panel) shrinks it — hence the -1 direction factor.
      const dir = -1;
      splitter.classList.add('dragging');
      document.body.style.cursor     = dim === 'width' ? 'col-resize' : 'row-resize';
      document.body.style.userSelect = 'none';

      const onMove = ev => {
        const delta = (ev[axisClient] - start) * dir;
        const next  = _clamp(startSize + delta, opts.min, opts.max);
        panel.style[dim] = next + 'px';
      };
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup',   onUp);
        splitter.classList.remove('dragging');
        document.body.style.cursor     = '';
        document.body.style.userSelect = '';
        const v = dim === 'width' ? panel.offsetWidth : panel.offsetHeight;
        try { localStorage.setItem(opts.key, String(v)); } catch (err) {}
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup',   onUp);
    });
    // Keyboard accessibility: focusable splitter; arrow keys nudge by 10px.
    splitter.tabIndex = 0;
    splitter.setAttribute('role', 'separator');
    splitter.addEventListener('keydown', ev => {
      const keyMap = dim === 'width'
        ? {ArrowLeft: +10, ArrowRight: -10}   // left widens, right narrows
        : {ArrowUp:   +10, ArrowDown:  -10};  // up widens,   down narrows
      const step = keyMap[ev.key];
      if (step === undefined) return;
      ev.preventDefault();
      const cur  = dim === 'width' ? panel.offsetWidth : panel.offsetHeight;
      const next = _clamp(cur + step, opts.min, opts.max);
      panel.style[dim] = next + 'px';
      try { localStorage.setItem(opts.key, String(next)); } catch (err) {}
    });
  }

  function init() {
    _restore('#right-panel', 'width',  RIGHT_MIN, RIGHT_MAX, KEY_RIGHT);
    _restore('#meta-panel',  'height', META_MIN,  META_MAX,  KEY_META);
    _wire('#split-right', '#right-panel', 'width',
          { min: RIGHT_MIN, max: RIGHT_MAX, key: KEY_RIGHT });
    _wire('#split-meta',  '#meta-panel',  'height',
          { min: META_MIN,  max: META_MAX,  key: KEY_META });
  }

  return { init };
})();
