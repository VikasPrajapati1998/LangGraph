// script.js — Blog home page

(function () {
  'use strict';

  // Animate cards on scroll
  const cards = document.querySelectorAll('.blog-card');
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 }
    );
    cards.forEach(function (card) {
      card.style.opacity = '0';
      card.style.transform = 'translateY(16px)';
      card.style.transition = 'opacity .4s ease, transform .4s ease';
      io.observe(card);
    });
  }
})();
