import '../css/editor_elm.scss';
import '../css/roster.scss';

// The roster page works without JavaScript: a chip is a link that follows its registrar, the filters are a
// form, and months are links. This makes following instant (pointing at a chip rings that registrar's chips;
// clicking follows them), applies the filters as they change, moves through the month with keys, and on a
// phone runs the list on into the next month as it scrolls and opens it at today.

const CHIP = '.rb-chip[data-r]';
const NARROW = window.matchMedia('(max-width: 47.99rem)');
// How long the pointer may rest between chips before the ring goes: long enough to cross a gap.
const LINGER = 250;

const ring = (colour) => `box-shadow:0 0 0 1.5px #fff,0 0 0 3px ${colour}`;

// The rules core/views/roster.py writes for following (follow_css), and the ring for pointing. One rule for
// the whole month, so pointing at a name repaints that registrar's chips and nothing else.
function followCss(follow, preview) {
  let css = '';
  if (follow) {
    css +=
      `#rb .rb-chip[data-r]:not([data-r="${follow}"]){border-color:var(--re-line);background-color:#fff;color:var(--re-muted)}` +
      `#rb .rb-chip[data-r="${follow}"]{${ring('var(--re-ink)')}}` +
      `#rb .rb-chip[data-r="${follow}"].is-folded{display:var(--rb-chip-display)}`;
  }
  if (preview && preview !== follow) {
    css += `#rb .rb-chip[data-r="${preview}"]{${ring('var(--re-accent)')}}`;
  }
  return css;
}

function counted(n, one, many) {
  return `${n} ${n === 1 ? one : many}`;
}

function sentence(parts) {
  if (parts.length < 2) return parts[0] || 'nothing';
  return `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}`;
}

function withParam(href, name, value) {
  const url = new URL(href, window.location.href);
  if (value) url.searchParams.set(name, value);
  else url.searchParams.delete(name);
  return url.toString();
}

function isVisible(element) {
  return element.getClientRects().length > 0;
}

function typing(event) {
  const target = event.target;
  return (
    target.isContentEditable ||
    ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName) ||
    event.ctrlKey ||
    event.metaKey ||
    event.altKey
  );
}

up.compiler('.roster-board', (board) => {
  board.classList.add('has-js');
  const style = board.querySelector('#rb-follow-css');
  let preview = '';
  let lingering = null;
  let filtersOpen = false;

  const followed = () => board.dataset.follow || '';

  function paint() {
    style.textContent = followCss(followed(), preview);
  }

  function setPreview(r) {
    clearTimeout(lingering);
    lingering = null;
    if (r !== preview) {
      preview = r;
      paint();
    }
  }

  function letGo() {
    if (preview && !lingering)
      lingering = setTimeout(() => setPreview(''), LINGER);
  }

  // "Following Will Gillespie: 13 on call, 1 day off and 2 days of leave in October". Only who is followed is
  // announced, when it changes; the counts change quietly as months load.
  function summary(follow) {
    const chips = [
      ...board.querySelectorAll(
        `.rb-day:not(.is-outside) .rb-chips ${CHIP}[data-r="${follow}"]`,
      ),
    ];
    const count = (kind) => chips.filter((c) => c.dataset.kind === kind).length;
    const parts = [];
    if (count('oncall')) parts.push(`${count('oncall')} on call`);
    if (count('off')) parts.push(counted(count('off'), 'day off', 'days off'));
    if (count('leave'))
      parts.push(counted(count('leave'), 'day of leave', 'days of leave'));
    const months = [...board.querySelectorAll('.rb-monthblock')].map(
      (block) => block.dataset.label,
    );
    const when =
      months.length > 1 ? `${months[0]} to ${months.at(-1)}` : months[0];
    return `${sentence(parts)} in ${when}`;
  }

  function nameOf(follow) {
    return (
      board.querySelector(`${CHIP}[data-r="${follow}"]`)?.dataset.name ||
      board.querySelector(`.rb-person option[value="${follow}"]`)
        ?.textContent ||
      'this registrar'
    );
  }

  function describe(announce) {
    const line = board.querySelector('.rb-following');
    if (!line) return;
    const follow = followed();
    line.classList.toggle('is-on', !!follow);
    if (!announce) {
      const counts = line.querySelector('.rb-following-count');
      if (counts && follow) counts.textContent = summary(follow);
      return;
    }
    const text = document.createElement('span');
    text.className = 'rb-following-text';
    text.setAttribute('aria-live', 'polite');
    if (!follow) {
      line.replaceChildren(text);
      return;
    }
    const name = document.createElement('strong');
    name.id = 'rb-following-name';
    name.textContent = nameOf(follow);
    text.append('Following ', name, ':');
    const counts = document.createElement('span');
    counts.className = 'rb-following-count';
    counts.textContent = summary(follow);
    const stop = document.createElement('a');
    stop.className = 're-btn re-btn--quiet rb-unfollow';
    stop.href = withParam(window.location.href, 'follow', '');
    stop.textContent = 'Stop following';
    line.replaceChildren(text, counts, stop);
  }

  // Keep the address, the person picker and the links to other months in step, so following survives
  // reloads, sharing and the next month.
  function setFollow(follow) {
    const before = followed();
    board.dataset.follow = follow;
    preview = '';
    paint();
    for (const chip of board.querySelectorAll(`${CHIP}[data-r="${before}"]`)) {
      chip.removeAttribute('aria-describedby');
    }
    for (const chip of board.querySelectorAll(`${CHIP}[data-r="${follow}"]`)) {
      chip.setAttribute('aria-describedby', 'rb-following-name');
    }
    describe(true);
    window.history.replaceState(
      window.history.state,
      '',
      withParam(window.location.href, 'follow', follow),
    );
    const picker = board.querySelector('.rb-person');
    if (picker) {
      picker.value = follow;
      picker.classList.toggle('is-narrowing', !!follow);
    }
    for (const link of board.querySelectorAll('a.rb-keep')) {
      link.href = withParam(link.href, 'follow', follow);
    }
    const goto = board.querySelector('.rb-goto');
    goto?.querySelector('input[name="follow"]')?.remove();
    if (goto && follow) {
      const input = document.createElement('input');
      Object.assign(input, { type: 'hidden', name: 'follow', value: follow });
      goto.prepend(input);
    }
    rove();
  }

  // The board is one stop for Tab; arrow keys move between chips: up and down within a day, left and right
  // to the days either side.
  const keyChips = () =>
    [...board.querySelectorAll('.rb-chips a.rb-chip')].filter(isVisible);

  function rove() {
    const chips = keyChips();
    for (const chip of chips) chip.tabIndex = -1;
    const follow = followed();
    const entry =
      (follow && chips.find((c) => c.dataset.r === follow)) ||
      chips.find((c) => c.closest('.rb-day.is-today')) ||
      chips[0];
    if (entry) entry.tabIndex = 0;
  }

  function moveTo(from, to) {
    if (!to) return;
    from.tabIndex = -1;
    to.tabIndex = 0;
    to.focus();
  }

  function onKeydown(event) {
    const chip = event.target.closest?.('.rb-chips a.rb-chip');
    if (!chip || typing(event)) return;
    const days = [...board.querySelectorAll('.rb-day')].filter(
      (day) => isVisible(day) && day.querySelector('.rb-chips a.rb-chip'),
    );
    const day = chip.closest('.rb-day');
    const inDay = (d) =>
      [...d.querySelectorAll('.rb-chips a.rb-chip')].filter(isVisible);
    const here = inDay(day);
    const index = here.indexOf(chip);
    const at = days.indexOf(day);
    let to = null;
    if (event.key === 'ArrowDown') {
      to = here[index + 1] || (days[at + 1] && inDay(days[at + 1])[0]);
    } else if (event.key === 'ArrowUp') {
      to = here[index - 1] || (days[at - 1] && inDay(days[at - 1]).at(-1));
    } else if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      const next = days[at + (event.key === 'ArrowRight' ? 1 : -1)];
      if (next) {
        const there = inDay(next);
        to = there[Math.min(index, there.length - 1)];
      }
    } else {
      return;
    }
    event.preventDefault();
    moveTo(chip, to);
  }

  // [ and ] step a month, t goes to today.
  function onPageKey(event) {
    if (typing(event)) return;
    const link = {
      '[': '.rb-prev[href]',
      ']': '.rb-next[href]',
      t: '.rb-today',
    }[event.key];
    if (!link) return;
    const target = board.querySelector(link);
    if (target) {
      event.preventDefault();
      target.click();
    }
  }

  function chipOf(event) {
    return event.target.closest?.(CHIP);
  }

  function onPointerOver(event) {
    if (event.pointerType !== 'mouse') return;
    const chip = chipOf(event);
    if (chip) setPreview(chip.dataset.r);
    else letGo();
  }

  function onFocusIn(event) {
    const chip = chipOf(event);
    if (chip) setPreview(chip.dataset.r);
  }

  function onClick(event) {
    const chip = chipOf(event);
    if (!chip) return;
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0)
      return;
    event.preventDefault();
    setFollow(chip.dataset.r === followed() ? '' : chip.dataset.r);
  }

  function onChange(event) {
    if (event.target.matches('.rb-person')) setFollow(event.target.value);
  }

  // One list open at a time; a click elsewhere or Escape closes it.
  function closePops(except) {
    for (const pop of board.querySelectorAll('.rb-pop[open]')) {
      if (pop !== except) pop.open = false;
    }
  }

  function onToggle(event) {
    const pop = event.target;
    if (
      pop.matches?.('.rb-pop') &&
      pop.open &&
      !(NARROW.matches && pop.matches('.rb-fold'))
    ) {
      closePops(pop);
    }
  }

  function onDocumentClick(event) {
    if (!event.target.closest('.rb-pop')) {
      for (const pop of board.querySelectorAll('.rb-pop[open]')) {
        if (!(NARROW.matches && pop.matches('.rb-fold'))) pop.open = false;
      }
    }
  }

  function onEscape(event) {
    if (event.key !== 'Escape') return;
    const pop =
      event.target.closest?.('.rb-pop[open]') ||
      board.querySelector('.rb-pop[open]');
    if (pop) {
      pop.open = false;
      pop.querySelector('summary').focus();
    }
  }

  // On a phone the filters fold behind a button.
  function onFilterToggle(event) {
    const button = event.target.closest('.rb-filter-toggle');
    if (!button) return;
    filtersOpen = !filtersOpen;
    showFilters();
  }

  function showFilters() {
    board
      .querySelector('.rb-filters')
      ?.classList.toggle('is-open', filtersOpen);
    board
      .querySelector('.rb-filter-toggle')
      ?.setAttribute('aria-expanded', String(filtersOpen));
  }

  function onInserted(event) {
    if (!board.contains(event.target) || event.target === board) return;
    showFilters();
    describe(false);
    rove();
  }

  board.addEventListener('pointerover', onPointerOver);
  board.addEventListener('pointerleave', letGo);
  board.addEventListener('focusin', onFocusIn);
  board.addEventListener('focusout', letGo);
  board.addEventListener('click', onClick);
  board.addEventListener('click', onFilterToggle);
  board.addEventListener('change', onChange);
  board.addEventListener('keydown', onKeydown);
  board.addEventListener('keydown', onEscape);
  board.addEventListener('toggle', onToggle, true);
  document.addEventListener('click', onDocumentClick);
  document.addEventListener('keydown', onPageKey);
  const offInserted = up.on('up:fragment:inserted', onInserted);

  paint();
  rove();

  // A phone opens at today, under the month's name.
  const today = board.querySelector('#rb-today');
  if (NARROW.matches && today && !window.location.hash) {
    window.requestAnimationFrame(() =>
      today.scrollIntoView({ block: 'start' }),
    );
  }

  return () => {
    clearTimeout(lingering);
    document.removeEventListener('click', onDocumentClick);
    document.removeEventListener('keydown', onPageKey);
    offInserted();
  };
});

// On a phone the list runs on: the next month loads under this one as its end comes into view, and the month
// before above it when asked. On a wide screen these links are hidden and the arrows page by month.
function loadMonth(link, target) {
  link.classList.remove('is-failed');
  return up
    .render({
      url: link.href,
      target,
      origin: link,
      history: false,
      scroll: false,
      failTarget: ':none',
      feedback: true,
    })
    .catch(() => {
      link.classList.add('is-failed');
      link.textContent = "Couldn't load it. Try again";
    });
}

up.compiler('.rb-later', (link) => {
  if (!NARROW.matches) return undefined;
  const load = () => loadMonth(link, '#rb-weeks:after, #rb-end');
  const observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        load();
      }
    },
    { rootMargin: '400px' },
  );
  observer.observe(link);
  link.addEventListener('click', (event) => {
    event.preventDefault();
    observer.disconnect();
    load();
  });
  return () => observer.disconnect();
});

up.compiler('.rb-earlier', (link) => {
  link.addEventListener('click', (event) => {
    if (!NARROW.matches) return;
    event.preventDefault();
    loadMonth(link, '#rb-weeks:before, #rb-start').then(() =>
      document
        .querySelector('.rb-monthblock')
        ?.scrollIntoView({ block: 'start' }),
    );
  });
});
