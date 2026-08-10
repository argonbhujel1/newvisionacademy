/* New Vision Academy – Main JS */
document.addEventListener('DOMContentLoaded', function () {
  document.documentElement.classList.add('js-anim');
  // Hero Slider
  const slides = document.querySelectorAll('.hero-slide');
  const dots = document.querySelectorAll('.hero-dot');
  let current = 0;
  let timer;

  function showSlide(index) {
    if (!slides.length) return;
    slides.forEach((s, i) => s.classList.toggle('active', i === index));
    dots.forEach((d, i) => d.classList.toggle('active', i === index));
    current = index;
  }

  function nextSlide() {
    showSlide((current + 1) % slides.length);
  }

  if (slides.length > 1) {
    timer = setInterval(nextSlide, 6000);
    dots.forEach((dot, i) => {
      dot.addEventListener('click', () => {
        clearInterval(timer);
        showSlide(i);
        timer = setInterval(nextSlide, 6000);
      });
    });
  }

  // Scroll reveal animations
  const animated = document.querySelectorAll('.animate-on-scroll');
  if ('IntersectionObserver' in window && animated.length) {
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    animated.forEach((el) => obs.observe(el));
  } else {
    animated.forEach((el) => el.classList.add('visible'));
  }

  // Stagger children in grids
  document.querySelectorAll('.row').forEach((row) => {
    const kids = row.querySelectorAll(':scope > [class*="col"].animate-on-scroll');
    kids.forEach((kid, i) => {
      kid.style.transitionDelay = (i * 0.08) + 's';
    });
  });

  // Lazy load images
  const lazyImages = document.querySelectorAll('img[data-src]');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src;
          img.classList.add('loaded');
          img.removeAttribute('data-src');
          observer.unobserve(img);
        }
      });
    }, { rootMargin: '100px' });
    lazyImages.forEach(img => observer.observe(img));
  } else {
    lazyImages.forEach(img => {
      img.src = img.dataset.src;
      img.classList.add('loaded');
    });
  }

  // Smooth scroll
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // Auto-dismiss alerts
  setTimeout(() => {
    document.querySelectorAll('.alert-dismissible').forEach(alert => {
      const btn = alert.querySelector('.btn-close');
      if (btn) btn.click();
    });
  }, 6000);

  // Cookie consent
  const cookieBanner = document.getElementById('cookieBanner');
  if (cookieBanner) {
    const cookieChoice = localStorage.getItem('nva_cookie_consent');
    if (!cookieChoice) {
      cookieBanner.style.display = 'block';
    }
    const acceptBtn = document.getElementById('cookieAccept');
    const declineBtn = document.getElementById('cookieDecline');
    if (acceptBtn) {
      acceptBtn.addEventListener('click', () => {
        localStorage.setItem('nva_cookie_consent', 'accepted');
        cookieBanner.style.display = 'none';
      });
    }
    if (declineBtn) {
      declineBtn.addEventListener('click', () => {
        localStorage.setItem('nva_cookie_consent', 'declined');
        cookieBanner.style.display = 'none';
      });
    }
  }

  // Newsletter popup
  const newsletterModalEl = document.getElementById('newsletterModal');
  if (newsletterModalEl && typeof bootstrap !== 'undefined') {
    let done = localStorage.getItem('nva_newsletter_done') || '';
    if (done.startsWith('dismissed_')) {
      const ts = parseInt(done.split('_')[1], 10);
      if (Date.now() - ts > 7 * 24 * 60 * 60 * 1000) {
        localStorage.removeItem('nva_newsletter_done');
        done = '';
      }
    }
    if (!done || done.startsWith('dismissed_') === false && done !== '1') {
      // show only if never subscribed; dismissed within 7 days stays hidden
    }
    if (done !== '1' && !done.startsWith('dismissed_')) {
      setTimeout(() => {
        try {
          const modal = new bootstrap.Modal(newsletterModalEl);
          modal.show();
        } catch (e) {}
      }, 2500);
    }
    const form = document.getElementById('newsletterForm');
    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('newsletterEmail').value.trim();
        const msgEl = document.getElementById('newsletterMsg');
        if (!email) return;
        try {
          const res = await fetch('/subscribe', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ email })
          });
          const data = await res.json();
          if (msgEl) {
            msgEl.textContent = data.message || 'Thank you!';
            msgEl.className = 'small ' + (data.ok ? 'text-success' : 'text-danger');
          }
          if (data.ok) {
            localStorage.setItem('nva_newsletter_done', '1');
            setTimeout(() => {
              const m = bootstrap.Modal.getInstance(newsletterModalEl);
              if (m) m.hide();
            }, 1500);
          }
        } catch (err) {
          if (msgEl) {
            msgEl.textContent = 'Something went wrong. Please try again.';
            msgEl.className = 'small text-danger';
          }
        }
      });
    }
    newsletterModalEl.addEventListener('hidden.bs.modal', () => {
      if (localStorage.getItem('nva_newsletter_done') !== '1') {
        localStorage.setItem('nva_newsletter_done', 'dismissed_' + Date.now());
      }
    });
  }
});
