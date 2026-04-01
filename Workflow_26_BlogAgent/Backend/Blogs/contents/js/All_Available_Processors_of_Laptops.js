// All_Available_Processors_of_Laptops.js — Blog post interactivity

(function () {
  'use strict';

  // ── Reading progress bar ──────────────────────────────────
  const bar = document.getElementById('readingBar');
  if (bar) {
    window.addEventListener('scroll', function () {
      const scrollTop    = window.scrollY;
      const docHeight    = document.documentElement.scrollHeight - window.innerHeight;
      const pct          = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      bar.style.width    = Math.min(pct, 100) + '%';
    }, { passive: true });
  }

  // ── Copy-code buttons ─────────────────────────────────────
  document.querySelectorAll('pre').forEach(function (pre) {
    const btn       = document.createElement('button');
    btn.className   = 'copy-btn';
    btn.textContent = 'Copy';
    pre.style.position = 'relative';
    pre.appendChild(btn);

    btn.addEventListener('click', function () {
      const code = pre.querySelector('code');
      const text = code ? code.innerText : pre.innerText;
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = 'Copied!';
        setTimeout(function () { btn.textContent = 'Copy'; }, 2000);
      }).catch(function () {
        btn.textContent = 'Error';
        setTimeout(function () { btn.textContent = 'Copy'; }, 2000);
      });
    });
  });

  // ── Smooth-scroll for anchor links ───────────────────────
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
})();
