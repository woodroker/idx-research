/* Animasi Tailwind (animate-*) + penguncian scroll. Dimuat setelah app.js. */
(() => {
  'use strict';
  const rm = false; // animasi tetap aktif walau Windows mematikan efek animasi (reduced-motion)
  const play = (el, cls) => { if (!el || rm) return; el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); el.addEventListener('animationend', () => el.classList.remove(cls), { once: true }); };

  // 1) fade in saat ganti tab (v1..v5) dan tab di panel emiten
  const tabs = new MutationObserver(m => m.forEach(r => { if (!r.target.hidden) play(r.target, 'animate-fadeIn'); }));
  ['v1', 'v2', 'v3', 'v4', 'v5'].forEach(id => { const e = document.getElementById(id); if (e) tabs.observe(e, { attributes: true, attributeFilter: ['hidden'] }); });
  document.addEventListener('click', e => {
    if (e.target.closest('.ptabs button')) document.querySelectorAll('#pn>:not(.phd):not(.ptabs)').forEach(el => { if (el.offsetParent) play(el, 'animate-fadeIn'); });
  });

  // 2) popup: slide dari kanan, kunci scroll halaman (hindari double scroll Y)
  const ov = document.getElementById('ov');
  if (ov) new MutationObserver(() => {
    const open = !ov.hidden;
    document.documentElement.classList.toggle('ov-open', open);
    if (open) play(document.getElementById('pn'), 'animate-slideInRight');
  }).observe(ov, { attributes: true, attributeFilter: ['hidden'] });

  // 3) dropdown saran: slide down + fade
  const sg = () => document.getElementById('sg');
  new MutationObserver(() => { const b = sg(); if (b && b.style.display === 'block' && !b.dataset.o) { b.dataset.o = 1; play(b, 'animate-slideDown'); } else if (b && b.style.display !== 'block') delete b.dataset.o; })
    .observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style'] });

  // 4) fadeInDown saat scroll ke bawah (hanya blok yang awalnya di bawah layar)
  const io = 'IntersectionObserver' in window && !rm ? new IntersectionObserver(es => es.forEach(en => {
    if (!en.isIntersecting) return;
    const el = en.target; io.unobserve(el); el.classList.remove('opacity-0'); play(el, 'animate-fadeInDown');
  }), { threshold: .06 }) : null;
  const scan = () => {
    if (!io) return;
    document.querySelectorAll('#mn details').forEach(el => {
      if (el.dataset.sr || !el.offsetParent) return;
      el.dataset.sr = 1;
      if (el.getBoundingClientRect().top > innerHeight) { el.classList.add('opacity-0'); io.observe(el); }
    });
  };
  scan();
  document.addEventListener('click', e => { if (e.target.closest('[data-v]')) setTimeout(scan, 60); });
  setTimeout(scan, 800);

  // 5) "Tampilkan lebih banyak" + pencarian: tinggi kontainer mengembang halus, baris baru muncul bertahap (glass + blur)
  const MORE = { more: ['#tb', 'tr'], dmore: ['#dtb', 'tr'], bmore: ['#btb', 'tr'] };
  const SRCH = { q: ['#tb', 'tr'], dq: ['#dtb', 'tr'], bq: ['#btb', 'tr'], sgq: ['#sgg', '.sgc'] };
  const rowsOf = cfg => { const h = document.querySelector(cfg[0]); return h ? [...h.querySelectorAll(':scope > ' + cfg[1])] : []; };
  const boxOf = cfg => { const h = document.querySelector(cfg[0]); return h && (h.closest('.tw') || h); };
  const glide = (cfg, stagger) => {
    if (rm) return;
    const box = boxOf(cfg); if (!box) return;
    const n = rowsOf(cfg).length, before = box.getBoundingClientRect().height;
    clearTimeout(box._fx); box.style.cssText = box.style.cssText.replace(/(height|overflow|transition)[^;]*;?/g, '');
    requestAnimationFrame(() => {
      const after = box.getBoundingClientRect().height;
      rowsOf(cfg).slice(stagger ? n : 0).forEach((el, i) => {
        el.style.animationDelay = Math.min(i * 35, 350) + 'ms';
        el.classList.add('fx-more-item');
        el.addEventListener('animationend', () => { el.classList.remove('fx-more-item'); el.style.animationDelay = ''; }, { once: true });
      });
      if (Math.abs(after - before) < 2) return;
      box.style.height = before + 'px'; box.style.overflow = 'hidden'; void box.offsetHeight;
      box.style.setProperty('transition', 'height .45s cubic-bezier(.2,.8,.2,1)', 'important'); box.style.height = after + 'px';
      box._fx = setTimeout(() => { box.style.height = ''; box.style.overflow = ''; box.style.transition = ''; }, 520);
    });
  };
  document.addEventListener('click', e => {
    const b = e.target.closest('#more,#dmore,#bmore,[data-tgmore]');
    if (b) glide(b.hasAttribute('data-tgmore') ? ['#tgbody', '.tr'] : MORE[b.id], true);
  }, true);
  document.addEventListener('input', e => { const c = SRCH[e.target.id]; if (c) glide(c, false); }, true);
})();
