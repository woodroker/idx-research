(() => {
  'use strict';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  let revealObserver;
  const dropdownTimers = new WeakMap();

  function bindHoverDropdown(details) {
    if (!canHover || details.dataset.fxHoverBound) return;
    details.dataset.fxHoverBound = '1';
    details.addEventListener('mouseenter', () => {
      clearTimeout(dropdownTimers.get(details));
      details.classList.remove('fx-hover-closing');
      if (!details.open) {
        details.open = true;
        details.dataset.fxOpenedByHover = '1';
      }
    });
    details.addEventListener('mouseleave', () => {
      if (!details.open || !details.dataset.fxOpenedByHover) return;
      clearTimeout(dropdownTimers.get(details));
      dropdownTimers.set(details, setTimeout(() => {
        details.classList.add('fx-hover-closing');
        dropdownTimers.set(details, setTimeout(() => {
          details.open = false;
          details.classList.remove('fx-hover-closing');
          delete details.dataset.fxOpenedByHover;
        }, reduceMotion ? 0 : 160));
      }, reduceMotion ? 0 : 90));
    });
    details.addEventListener('click', event => {
      if (event.target.closest('summary')) delete details.dataset.fxOpenedByHover;
    });
  }
  function scanDropdowns(root = document) {
    if (root instanceof HTMLDetailsElement) bindHoverDropdown(root);
    root.querySelectorAll?.('details').forEach(bindHoverDropdown);
  }

  function scanReveal(root = document) {
    if (reduceMotion) return;
    const nodes = [];
    if (root instanceof Element && root.matches('.cd,.k,.rb,.fu-c,.fu-q,.fu-r,#pnDec')) nodes.push(root);
    if (root.querySelectorAll) nodes.push(...root.querySelectorAll('.cd,.k,.rb,.fu-c,.fu-q,.fu-r,#pnDec'));
    for (const el of nodes) {
      if (el.classList.contains('fx-reveal')) continue;
      el.classList.add('fx-reveal');
      if (revealObserver) revealObserver.observe(el);
      else el.classList.add('fx-visible');
    }
  }

  if ('IntersectionObserver' in window && !reduceMotion) {
    revealObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('fx-visible');
          revealObserver.unobserve(entry.target);
        }
      }
    }, { threshold: .08, rootMargin: '0px 0px -24px 0px' });
  }
  scanDropdowns();
  scanReveal();
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType === Node.ELEMENT_NODE) { scanDropdowns(node); scanReveal(node); }
  }))).observe(document.body, { childList: true, subtree: true });

  document.addEventListener('click', event => {
    const tab = event.target.closest('[data-v]');
    if (tab && !reduceMotion) {
      const view = document.getElementById('v' + tab.dataset.v);
      if (view) {
        view.classList.remove('fx-tab-enter');
        void view.offsetWidth;
        view.classList.add('fx-tab-enter');
      }
    }
  });

  const modalObserver = new MutationObserver(() => {
    const overlay = document.getElementById('ov');
    const open = !!overlay && !overlay.hidden;
    document.body.classList.toggle('screener-modal-open', open);
    if (open) document.getElementById('pn')?.classList.add('fx-modal-enter');
  });
  const overlay = document.getElementById('ov');
  if (overlay) modalObserver.observe(overlay, { attributes: true, attributeFilter: ['hidden'] });

  // Add a contextual combined-decision/market-phase column using existing calculations only.
  function decorateAccumulationTable() {
    const body = document.getElementById('tb');
    const table = body?.closest('table');
    const head = table?.querySelector('thead tr');
    if (!body || !head || typeof window.KEP !== 'function') return;
    let th = head.querySelector('[data-fx-decision]');
    if (!th) {
      th = document.createElement('th');
      th.className = 'fx-decision-head';
      th.dataset.fxDecision = '1';
      th.textContent = 'Keputusan gabungan';
      head.append(th);
    }
    const tone = { BUY: 'var(--up)', HOLD: '#60a5fa', WAIT: '#f59e0b', SELL: 'var(--dn)' };
    for (const row of body.querySelectorAll('tr[data-c]')) {
      const code = row.dataset.c;
      let cell = row.querySelector('.fx-decision');
      if (!cell) { cell = document.createElement('td'); cell.className = 'fx-decision'; row.append(cell); }
      try {
        const decision = window.KEP(code);
        const phase = window.BM?.[code]?.ph;
        const phaseLabel = phase?.p && window.PCC?.ph?.[phase.p]?.[0] ? window.PCC.ph[phase.p][0] : '—';
        cell.innerHTML = `<b style="color:${tone[decision.act] || 'inherit'}">${decision.act} · ${decision.K == null ? '—' : Math.round(decision.K)}</b><small>Fase pasar: ${phaseLabel}</small>`;
        cell.title = (decision.why || '') + ' · Fase pasar hanya konteks, tidak mengubah rumus keputusan.';
      } catch (_) { cell.textContent = '—'; }
    }
  }
  function attachTableRefresh() {
    try {
      const original = window.draw;
      if (typeof original === 'function' && !original.__fxWrapped) {
        const wrapped = function (...args) {
          const result = original.apply(this, args);
          decorateAccumulationTable();
          return result;
        };
        wrapped.__fxWrapped = true;
        window.draw = wrapped;
      }
    } catch (_) {}
  }
  attachTableRefresh();
  setInterval(() => { attachTableRefresh(); decorateAccumulationTable(); }, 5000);
})();
