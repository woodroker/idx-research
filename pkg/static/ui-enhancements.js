(() => {
  'use strict';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  let revealObserver;
  const dropdownTimers = new WeakMap();
  const investorNames = [
    [/^local\s+corporate\b/i, 'Lokal · Korporasi'],
    [/^local\s+individual\b/i, 'Lokal · Individu'],
    [/^local\s+mutual\s+funds\b/i, 'Lokal · Reksa Dana'],
    [/^local\s+investment\s+advis/i, 'Lokal · Penasihat Investasi'],
    [/^local\s+commanditaire\s+ve/i, 'Lokal · Persekutuan Komanditer'],
    [/^foreign\s+corporate\b/i, 'Asing · Korporasi'],
    [/^foreign\s+individual\b/i, 'Asing · Individu'],
    [/^foreign\s+mutual\s+funds\b/i, 'Asing · Reksa Dana'],
    [/^foreign\s+investment\s+advis/i, 'Asing · Penasihat Investasi'],
    [/^foreign\s+commanditaire\s+ve/i, 'Asing · Persekutuan Komanditer']
  ];
  function formatInvestorLabel(label) {
    const clean = label.replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
    for (const [pattern, text] of investorNames) {
      if (pattern.test(clean)) {
        const suffix = clean.match(/\([^)]*\)/)?.[0] || '';
        return text + (suffix ? ' ' + suffix.replace(/^\(ID\)$/i, '(Indonesia)') : '');
      }
    }
    return clean.replace(/\b(Local|Foreign)\b/i, word => word.toLowerCase() === 'local' ? 'Lokal' : 'Asing');
  }
  function fixInvestorComposition(root = document) {
    const headings = [];
    if (root instanceof Element && root.matches('#pn h3')) headings.push(root);
    root.querySelectorAll?.('#pn h3').forEach(el => headings.push(el));
    for (const heading of headings) {
      if (!/^Komposisi klasifikasi investor\b/i.test(heading.textContent.trim())) continue;
      let node = heading.nextElementSibling;
      while (node && !/^H[1-3]$/.test(node.tagName)) {
        if (node.classList.contains('cp')) {
          const label = node.querySelector(':scope > span:first-child');
          if (label && label.dataset.fxLabelDone !== '1') {
            label.textContent = formatInvestorLabel(label.textContent);
            label.dataset.fxLabelDone = '1'; label.title = label.textContent;
          }
        }
        node = node.nextElementSibling;
      }
    }
  }
  function bindHoverDropdown(details) {
    if (!canHover || details.dataset.fxHoverBound) return;
    details.dataset.fxHoverBound = '1';
    details.addEventListener('mouseenter', () => {
      clearTimeout(dropdownTimers.get(details)); details.classList.remove('fx-hover-closing');
      if (!details.open) { details.open = true; details.dataset.fxOpenedByHover = '1'; }
    });
    details.addEventListener('mouseleave', () => {
      if (!details.open || !details.dataset.fxOpenedByHover) return;
      clearTimeout(dropdownTimers.get(details));
      dropdownTimers.set(details, setTimeout(() => {
        details.classList.add('fx-hover-closing');
        dropdownTimers.set(details, setTimeout(() => {
          details.open = false; details.classList.remove('fx-hover-closing');
          delete details.dataset.fxOpenedByHover;
        }, reduceMotion ? 0 : 160));
      }, reduceMotion ? 0 : 90));
    });
    details.addEventListener('click', event => { if (event.target.closest('summary')) delete details.dataset.fxOpenedByHover; });
  }
  function scan(root = document) {
    if (root instanceof HTMLDetailsElement) bindHoverDropdown(root);
    root.querySelectorAll?.('details').forEach(bindHoverDropdown);
    fixInvestorComposition(root);
  }
  function scanReveal(root = document) {
    if (reduceMotion) return;
    const nodes = [];
    if (root instanceof Element && root.matches('.cd,.k,.rb,.fu-c,.fu-q,.fu-r,#pnDec')) nodes.push(root);
    root.querySelectorAll?.('.cd,.k,.rb,.fu-c,.fu-q,.fu-r,#pnDec').forEach(el => nodes.push(el));
    for (const el of nodes) {
      if (el.classList.contains('fx-reveal')) continue;
      el.classList.add('fx-reveal');
      if (revealObserver) revealObserver.observe(el); else el.classList.add('fx-visible');
    }
  }
  if ('IntersectionObserver' in window && !reduceMotion) {
    revealObserver = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add('fx-visible'); revealObserver.unobserve(entry.target); }
    }), { threshold:.08, rootMargin:'0px 0px -24px 0px' });
  }
  scan(); scanReveal();
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType === Node.ELEMENT_NODE) { scan(node); scanReveal(node); }
  }))).observe(document.body, { childList:true, subtree:true });
  document.addEventListener('click', event => {
    const tab = event.target.closest('[data-v]');
    if (tab && !reduceMotion) {
      const view = document.getElementById('v' + tab.dataset.v);
      if (view) { view.classList.remove('fx-tab-enter'); void view.offsetWidth; view.classList.add('fx-tab-enter'); }
    }
  });
  const overlay = document.getElementById('ov');
  if (overlay) new MutationObserver(() => {
    const open = !overlay.hidden;
    document.body.classList.toggle('screener-modal-open', open);
    if (open) document.getElementById('pn')?.classList.add('fx-modal-enter');
  }).observe(overlay, { attributes:true, attributeFilter:['hidden'] });
  function decorateAccumulationTable() {
    const body = document.getElementById('tb'), table = body?.closest('table'), head = table?.querySelector('thead tr');
    if (!body || !head || typeof window.KEP !== 'function') return;
    let th = head.querySelector('[data-fx-decision]');
    if (!th) { th = document.createElement('th'); th.className='fx-decision-head'; th.dataset.fxDecision='1'; th.textContent='Keputusan gabungan'; head.append(th); }
    const tone = { BUY:'var(--up)', HOLD:'#60a5fa', WAIT:'#f59e0b', SELL:'var(--dn)' };
    for (const row of body.querySelectorAll('tr[data-c]')) {
      const code = row.dataset.c;
      let cell = row.querySelector('.fx-decision');
      if (!cell) { cell = document.createElement('td'); cell.className='fx-decision'; row.append(cell); }
      try {
        const decision = window.KEP(code), phase = window.BM?.[code]?.ph;
        const phaseLabel = phase?.p && window.PCC?.ph?.[phase.p]?.[0] ? window.PCC.ph[phase.p][0] : '—';
        cell.innerHTML = `<b style="color:${tone[decision.act] || 'inherit'}">${decision.act} · ${decision.K == null ? '—' : Math.round(decision.K)}</b><small>Fase pasar: ${phaseLabel}</small>`;
        cell.title = (decision.why || '') + ' · Fase pasar hanya konteks, tidak mengubah rumus keputusan.';
      } catch (_) { cell.textContent='—'; }
    }
  }
  function attachTableRefresh() {
    const original = window.draw;
    if (typeof original !== 'function' || original.__fxWrapped) return;
    const wrapped = function (...args) { const result=original.apply(this,args); decorateAccumulationTable(); return result; };
    wrapped.__fxWrapped=true; window.draw=wrapped;
  }
  // Rebrand browser tab and visible dashboard heading without replacing the large HTML template.
  document.title = 'IDX Research';
  const title = document.querySelector('#mn > h1');
  if (title) title.textContent = 'IDX Research';
  attachTableRefresh();
  setInterval(() => { attachTableRefresh(); decorateAccumulationTable(); fixInvestorComposition(document); }, 5000);
})();
