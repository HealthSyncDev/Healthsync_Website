const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

const siteHeader = document.querySelector('.site-header');

if (siteHeader) {
  /* ponytail: sticky docks at top:16px; class only densifies glass */
  const syncStuck = () => {
    siteHeader.classList.toggle('is-stuck', siteHeader.getBoundingClientRect().top <= 17);
  };
  syncStuck();
  window.addEventListener('scroll', syncStuck, { passive: true });

  if (!reduceMotion) {
    let rippleTimer = 0;
    siteHeader.addEventListener('pointermove', (event) => {
      const rect = siteHeader.getBoundingClientRect();
      siteHeader.style.setProperty('--mx', `${((event.clientX - rect.left) / rect.width) * 100}%`);
      siteHeader.style.setProperty('--my', `${((event.clientY - rect.top) / rect.height) * 100}%`);
    });
    siteHeader.addEventListener('pointerenter', () => {
      siteHeader.classList.remove('is-rippling');
      // restart CSS animation without reading layout in a hot path
      requestAnimationFrame(() => siteHeader.classList.add('is-rippling'));
      clearTimeout(rippleTimer);
      rippleTimer = setTimeout(() => siteHeader.classList.remove('is-rippling'), 900);
    });
  }
}

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener('click', (event) => {
    const href = link.getAttribute('href');
    const target = href && document.querySelector(href);
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: 'smooth' });
  });
});

const networkFlow = document.querySelector('.network-flow');
const bookingFlow = networkFlow?.querySelector('.booking-flow');
const bookingPaths = bookingFlow?.querySelector('.booking-paths');
const otaLanes = networkFlow?.querySelector('.ota-lanes');
const cautionLayer = networkFlow?.querySelector('.caution-layer');

const CAUTION_BOOKINGS = ['one', 'two', 'three', 'four', 'five'];
const PATH_SAMPLES = 40;

function connectBookingPaths() {
  if (!bookingFlow || !bookingPaths) return;

  const flowRect = bookingFlow.getBoundingClientRect();
  const endX = flowRect.width / 2;
  const lowerJoinY = flowRect.height * (455 / 520);
  const upperJoinY = flowRect.height * (415 / 520);
  bookingPaths.setAttribute('viewBox', `0 0 ${flowRect.width} ${flowRect.height}`);

  const connections = [...bookingPaths.querySelectorAll('path[data-booking]')]
    .map((path) => {
      const booking = path.dataset.booking;
      const avatar = bookingFlow.querySelector(`.booking-${booking} .avatar`);
      if (!avatar) return null;
      const avatarRect = avatar.getBoundingClientRect();
      return {
        path,
        booking,
        startX: avatarRect.left + avatarRect.width / 2 - flowRect.left,
        startY: avatarRect.bottom - flowRect.top - 1,
      };
    })
    .filter(Boolean);

  // ponytail: funnel; outer c2 stays wide so it doesn't hug the mid path
  connections.forEach(({ path, booking, startX, startY }) => {
    const isOuter = booking === 'one' || booking === 'five';
    const endY = isOuter ? lowerJoinY : upperJoinY;
    const midY = startY + (endY - startY) * (isOuter ? 0.62 : 0.45);
    const c2x = endX + (startX - endX) * (isOuter ? 0.42 : 0.12);
    path.setAttribute(
      'd',
      `M ${startX} ${startY} C ${startX} ${midY}, ${c2x} ${midY}, ${endX} ${endY}`
    );
  });

  bookingPaths.querySelector('.flow-stem')?.setAttribute('d', `M ${endX} ${upperJoinY} V ${lowerJoinY}`);
}

/** Pre-sampled path points — zero getPointAtLength / layout reads in the RAF loop. */
let cautionCache = null;
let cautionRunning = false;
let networkVisible = true;

function samplePath(path) {
  const fanLen = path.getTotalLength();
  if (!fanLen) return null;
  const pts = new Float32Array((PATH_SAMPLES + 1) * 2);
  for (let i = 0; i <= PATH_SAMPLES; i++) {
    const p = path.getPointAtLength((fanLen * i) / PATH_SAMPLES);
    pts[i * 2] = p.x;
    pts[i * 2 + 1] = p.y;
  }
  return { fanLen, pts };
}

function pointOnSample(sampled, dist) {
  const t = Math.max(0, Math.min(1, dist / sampled.fanLen));
  const idx = t * PATH_SAMPLES;
  const i = Math.min(PATH_SAMPLES - 1, Math.floor(idx));
  const f = idx - i;
  const a = i * 2;
  const b = (i + 1) * 2;
  return {
    x: sampled.pts[a] + (sampled.pts[b] - sampled.pts[a]) * f,
    y: sampled.pts[a + 1] + (sampled.pts[b + 1] - sampled.pts[a + 1]) * f,
  };
}

function refreshCautionCache() {
  if (!networkFlow || !cautionLayer || !bookingPaths || !bookingFlow) return;
  const netRect = networkFlow.getBoundingClientRect();
  const bookRect = bookingFlow.getBoundingClientRect();
  cautionLayer.setAttribute('viewBox', `0 0 ${netRect.width} ${netRect.height}`);
  const pill = otaLanes?.querySelector('.ota-end-pill');
  const endY = pill
    ? pill.getBoundingClientRect().top - netRect.top
    : netRect.height - 20;
  const paths = Object.create(null);
  for (const booking of CAUTION_BOOKINGS) {
    const path = bookingPaths.querySelector(`path[data-booking="${booking}"]`);
    if (!path) continue;
    const sampled = samplePath(path);
    if (!sampled) continue;
    const hub = pointOnSample(sampled, sampled.fanLen);
    paths[booking] = { ...sampled, hubX: hub.x, hubY: hub.y };
  }
  cautionCache = {
    ox: bookRect.left - netRect.left,
    oy: bookRect.top - netRect.top,
    cx: netRect.width / 2,
    endY,
    paths,
  };
}

function cautionPoint(booking, t) {
  const entry = cautionCache?.paths[booking];
  if (!entry || !cautionCache) return null;

  const { ox, oy, cx, endY } = cautionCache;
  const hubY = entry.hubY + oy;
  const vert = Math.max(endY - hubY, 1);
  const total = entry.fanLen + vert;
  const progress = t % 1;
  let d = progress * total;
  let x;
  let y;

  if (d <= entry.fanLen) {
    const fan = pointOnSample(entry, d);
    x = fan.x + ox;
    y = fan.y + oy;
  } else {
    d -= entry.fanLen;
    x = cx;
    y = hubY + d;
  }

  const fade = progress < 0.78 ? 1 : 1 - (progress - 0.78) / 0.22;
  return { x, y, opacity: Math.max(0, fade) };
}

function tickCautions(now) {
  if (!cautionRunning) return;
  if (!networkVisible || document.hidden || !cautionCache) {
    requestAnimationFrame(tickCautions);
    return;
  }

  for (let i = 0; i < CAUTION_BOOKINGS.length; i++) {
    const booking = CAUTION_BOOKINGS[i];
    const icon = cautionLayer.querySelector(`[data-caution="${booking}"]`);
    if (!icon) continue;
    const p = cautionPoint(booking, now / 9000 + i * 0.2);
    if (!p) continue;
    icon.setAttribute('transform', `translate(${p.x} ${p.y})`);
    icon.setAttribute('opacity', String(p.opacity));
  }

  requestAnimationFrame(tickCautions);
}

const relayoutNetwork = () => {
  connectBookingPaths();
  // ponytail: read geometry after paint so path writes don't force sync reflow
  requestAnimationFrame(refreshCautionCache);
};

connectBookingPaths();
requestAnimationFrame(() => {
  refreshCautionCache();
  cautionRunning = true;
  requestAnimationFrame(tickCautions);
});
if (bookingFlow) new ResizeObserver(relayoutNetwork).observe(bookingFlow);
if (networkFlow) {
  new ResizeObserver(relayoutNetwork).observe(networkFlow);
  new IntersectionObserver(
    ([entry]) => {
      networkVisible = entry?.isIntersecting ?? true;
    },
    { rootMargin: '80px' }
  ).observe(networkFlow);
}
window.addEventListener('resize', relayoutNetwork);

/* ponytail: page dots + autoplay; controls stay */
const bindCarousel = (track, grid, ctrl, cardSel) => {
  const dotsWrap = ctrl?.querySelector('.slider-dots');
  const btns = ctrl ? [...ctrl.querySelectorAll('.carousel-btn')] : [];
  if (!track || !grid || !dotsWrap) return;

  const cards = [...grid.querySelectorAll(cardSel)];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let perPage = 1;
  let pages = 1;
  let timer = 0;
  /** @type {number[]} */
  let pageLefts = [0];

  const measure = () => {
    const w = cards[0]?.offsetWidth || 1;
    const gap = parseFloat(getComputedStyle(track).gap) || 0;
    perPage = Math.max(1, Math.round((track.clientWidth + gap) / (w + gap)));
    pages = Math.max(1, Math.ceil(cards.length / perPage));
    pageLefts = Array.from({ length: pages }, (_, p) => {
      const card = cards[Math.min(p * perPage, cards.length - 1)];
      return card.offsetLeft;
    });
    dotsWrap.innerHTML = Array.from({ length: pages }, (_, i) =>
      `<button type="button" aria-label="Go to page ${i + 1}"${i === 0 ? ' class="is-active"' : ''}></button>`
    ).join('');
    [...dotsWrap.querySelectorAll('button')].forEach((dot, i) => {
      dot.addEventListener('click', () => {
        goPage(i);
        bump();
      });
    });
    sync();
  };

  const pageIndex = () => {
    const left = track.scrollLeft;
    let best = 0;
    let dist = Infinity;
    for (let p = 0; p < pages; p++) {
      const d = Math.abs(pageLefts[p] - left);
      if (d < dist) {
        dist = d;
        best = p;
      }
    }
    return best;
  };

  const goPage = (p) => {
    const n = ((p % pages) + pages) % pages;
    track.scrollTo({ left: pageLefts[n] || 0, behavior: 'smooth' });
  };

  const sync = () => {
    const p = pageIndex();
    [...dotsWrap.querySelectorAll('button')].forEach((dot, n) => {
      dot.classList.toggle('is-active', n === p);
    });
  };

  const play = () => {
    clearInterval(timer);
    if (reduce || pages < 2) return;
    timer = setInterval(() => goPage(pageIndex() + 1), 4200);
  };

  const bump = () => {
    clearInterval(timer);
    play();
  };

  track.addEventListener('scroll', () => requestAnimationFrame(sync), { passive: true });
  btns.forEach((btn) => {
    btn.addEventListener('click', () => {
      goPage(pageIndex() + Number(btn.dataset.dir));
      bump();
    });
  });
  [track, ctrl].forEach((el) => {
    el?.addEventListener('pointerenter', () => clearInterval(timer));
    el?.addEventListener('pointerleave', play);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearInterval(timer);
    else play();
  });
  new ResizeObserver(measure).observe(track);
  measure();
  play();
};
bindCarousel(
  document.querySelector('.benefit-scroller'),
  document.querySelector('.benefit-grid'),
  document.querySelector('.benefits .carousel-ctrl'),
  '.benefit'
);
bindCarousel(
  document.querySelector('.how-track'),
  document.querySelector('.how-track'),
  document.querySelector('.how-ctrl'),
  '.how-card'
);

// ponytail: QR spotlight + drift — viewport % only (no per-frame getBoundingClientRect)
const shell = document.querySelector('.site-shell');
const finePointer = matchMedia('(pointer:fine)').matches;

if (shell && finePointer && !reduceMotion) {
  let x = innerWidth / 2;
  let y = innerHeight / 2;
  let rx = x;
  let ry = y;
  let dirty = true;
  addEventListener(
    'pointermove',
    (e) => {
      x = e.clientX;
      y = e.clientY;
      dirty = true;
    },
    { passive: true }
  );
  (function tickDots() {
    if (dirty || Math.abs(rx - x) > 0.1 || Math.abs(ry - y) > 0.1) {
      rx += (x - rx) * 0.1;
      ry += (y - ry) * 0.1;
      const nx = rx / innerWidth - 0.5;
      const ny = ry / innerHeight - 0.5;
      shell.style.setProperty('--qx', `${nx * 72}px`);
      shell.style.setProperty('--qy', `${ny * 56}px`);
      shell.style.setProperty('--sx', `${(rx / innerWidth) * 100}%`);
      shell.style.setProperty('--sy', `${(ry / innerHeight) * 100}%`);
      dirty = Math.abs(rx - x) > 0.1 || Math.abs(ry - y) > 0.1;
    }
    requestAnimationFrame(tickDots);
  })();
}

const hsWord = document.querySelector('.hs-dot-word');
const growth = document.querySelector('.growth');
if (hsWord && growth && finePointer && !reduceMotion) {
  growth.addEventListener(
    'pointermove',
    (e) => {
      const r = hsWord.getBoundingClientRect();
      hsWord.classList.add('is-spot');
      hsWord.style.setProperty('--hx', `${((e.clientX - r.left) / r.width) * 100}%`);
      hsWord.style.setProperty('--hy', `${((e.clientY - r.top) / r.height) * 100}%`);
    },
    { passive: true }
  );
  growth.addEventListener('pointerleave', () => hsWord.classList.remove('is-spot'));
}

if (finePointer && !reduceMotion) {
  const dot = Object.assign(document.createElement('div'), { className: 'cursor-dot' });
  const ring = Object.assign(document.createElement('div'), { className: 'cursor-ring' });
  document.body.append(dot, ring);
  document.documentElement.classList.add('has-cursor');
  let x = innerWidth / 2;
  let y = innerHeight / 2;
  let rx = x;
  let ry = y;
  const hoverSel = 'a,button,[role="button"],input,textarea,select,label,.cta';
  addEventListener('pointermove', (e) => {
    x = e.clientX;
    y = e.clientY;
    document.documentElement.classList.toggle('is-hover', !!e.target.closest?.(hoverSel));
  });
  addEventListener('pointerdown', () => document.documentElement.classList.add('is-down'));
  addEventListener('pointerup', () => document.documentElement.classList.remove('is-down'));
  (function tick() {
    rx += (x - rx) * 0.16;
    ry += (y - ry) * 0.16;
    dot.style.transform = `translate(${x}px,${y}px)`;
    ring.style.transform = `translate(${rx}px,${ry}px)`;
    requestAnimationFrame(tick);
  })();
}

/* ponytail: CSS/IO reveals — no GSAP/Lenis (dev Lighthouse can't hit 100 with them) */
function splitWords(el) {
  const walk = (node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const parts = node.textContent.split(/(\s+)/);
      const frag = document.createDocumentFragment();
      parts.forEach((part) => {
        if (!part) return;
        if (/^\s+$/.test(part)) {
          frag.append(document.createTextNode(part));
          return;
        }
        const span = document.createElement('span');
        span.className = 'fx-word';
        span.textContent = part;
        frag.append(span);
      });
      node.replaceWith(frag);
    } else if (node.nodeType === Node.ELEMENT_NODE && node.tagName !== 'BR') {
      [...node.childNodes].forEach(walk);
    }
  };
  walk(el);
  return el.querySelectorAll('.fx-word');
}

if (!reduceMotion) {
  const heroTitle = document.querySelector('#hero-title');
  if (heroTitle) {
    splitWords(heroTitle).forEach((word, i) => {
      word.style.setProperty('--d', `${0.15 + i * 0.035}s`);
      word.classList.add('fx-hero-word');
    });
  }

  document.querySelectorAll('main h2').forEach((h2) => {
    splitWords(h2).forEach((word, i) => {
      word.style.setProperty('--d', `${i * 0.03}s`);
    });
    h2.classList.add('fx-reveal-words');
  });

  document
    .querySelectorAll(
      '.section-pill:not(.hero-pill), .timeline-event, .timeline-summary, .how-card, .benefit, .edge-card, .closing-sub, .closing .orange-button, .site-footer'
    )
    .forEach((el) => el.classList.add('fx-reveal'));

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-in');
        io.unobserve(entry.target);
      });
    },
    { rootMargin: '0px 0px -10% 0px', threshold: 0.08 }
  );
  document.querySelectorAll('.fx-reveal, .fx-reveal-words').forEach((el) => io.observe(el));
}
