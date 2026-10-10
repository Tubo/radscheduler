import '../css/editor_elm.scss';
import '../css/leave_requests.scss';

// The Elm page is built by elm-watch into static/elm-build/leave_requests.js, loaded by its own script tag
// before this bundle; in development `elm-watch hot` reloads it in place.
const { Elm } = window;
if (!Elm?.LeaveRequests) {
  throw new Error(
    'The leave requests page is not built: run `pnpm build`, or `devenv up` for elm-watch.',
  );
}

// The page fills the window below the navbar, as the roster editor does.
function fitToWindow() {
  const page =
    document.querySelector('.leave-requests') ||
    document.getElementById('leave-requests-app');
  const top = page.getBoundingClientRect().top + window.scrollY;
  document.documentElement.style.setProperty('--re-top', `${top}px`);
}

const app = Elm.LeaveRequests.init({
  node: document.getElementById('leave-requests-app'),
  flags: {
    ...JSON.parse(document.getElementById('leave-requests-flags').textContent),
    // The overview's filters, and whether approval mode is open, live in the address.
    query: window.location.search,
  },
});

fitToWindow();
window.addEventListener('resize', fitToWindow);

app.ports.replaceQuery.subscribe((query) => {
  const url = query
    ? `${window.location.pathname}?${query}`
    : window.location.pathname;
  window.history.replaceState(window.history.state, '', url);
});

// Keep the navbar's pill, the requests waiting on you, in step with the decisions made here. It is drawn by
// the server as in navbar_link.html: hidden words either side of the number, so it reads "16 waiting on you".
app.ports.waitingChanged.subscribe((count) => {
  const link = document.querySelector(
    `.navbar a.nav-link[href="${window.location.pathname}"]`,
  );
  if (!link) return;
  let pill = link.querySelector('.navbar-count');
  if (!count) {
    pill?.remove();
    return;
  }
  const label = pill?.lastElementChild?.textContent || ' waiting on you';
  if (!pill) {
    pill = document.createElement('span');
    pill.className = 'navbar-count';
    link.append(pill);
  }
  const hidden = (text) => {
    const span = document.createElement('span');
    span.className = 'visually-hidden';
    span.textContent = text;
    return span;
  };
  pill.replaceChildren(hidden(', '), String(count), hidden(label));
});

// "How it works" is a menu: a click elsewhere or Escape closes it, as it would any other.
document.addEventListener('click', (event) => {
  for (const menu of document.querySelectorAll('.lr-help[open]')) {
    if (!menu.contains(event.target)) menu.open = false;
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  const menu = document.querySelector('.lr-help[open]');
  if (menu) {
    menu.open = false;
    menu.querySelector('summary').focus();
  }
});
