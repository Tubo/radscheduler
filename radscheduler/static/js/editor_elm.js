import '../css/editor_elm.scss';

// The Elm app is built by elm-watch into static/elm-build/editor.js, loaded by its own script tag before
// this bundle; in development `elm-watch hot` reloads it in place, keeping the editor's state.
const { Elm } = window;
if (!Elm?.Editor) {
  throw new Error(
    'The Elm editor is not built: run `pnpm build`, or `devenv up` for elm-watch.',
  );
}

const FILTERS_KEY = 'radscheduler.editor.filters';

// Filters are a per-browser convenience; storage can be unavailable, so never depend on it.
function savedFilters() {
  try {
    return JSON.parse(localStorage.getItem(FILTERS_KEY)) || {};
  } catch {
    return {};
  }
}

const node = document.getElementById('editor-app');
const flags = {
  ...JSON.parse(document.getElementById('editor-flags').textContent),
  ...savedFilters(),
};

// The editor fills the window below the navbar.
function fitToWindow() {
  const editor = document.querySelector('.roster-editor') || node;
  const top = editor.getBoundingClientRect().top + window.scrollY;
  document.documentElement.style.setProperty('--re-top', `${top}px`);
}
fitToWindow();
window.addEventListener('resize', fitToWindow);

const app = Elm.Editor.init({ node, flags });

app.ports.saveFilters.subscribe((filters) => {
  try {
    localStorage.setItem(FILTERS_KEY, JSON.stringify(filters));
  } catch {
    // Not saved; the filters still apply until the page reloads.
  }
});

// Dragging with the mouse scrolls the roster, like a map. A press only becomes a drag once it has moved a
// few pixels, so clicks still open a day and Shift-click still selects; the click that ends a drag is dropped.
const DRAG_THRESHOLD = 5;
let pan = null;

document.addEventListener('pointerdown', (event) => {
  const scroller = event.target.closest?.('.re-scroll');
  if (
    !scroller ||
    event.pointerType !== 'mouse' ||
    event.button !== 0 ||
    event.shiftKey ||
    event.ctrlKey ||
    event.metaKey ||
    event.altKey ||
    event.target.closest('input, select, textarea')
  ) {
    return;
  }
  pan = {
    scroller,
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    left: scroller.scrollLeft,
    top: scroller.scrollTop,
    dragging: false,
  };
});

document.addEventListener('pointermove', (event) => {
  if (!pan || event.pointerId !== pan.pointerId) return;
  const dx = event.clientX - pan.x;
  const dy = event.clientY - pan.y;
  if (!pan.dragging) {
    if (Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    pan.dragging = true;
    pan.scroller.classList.add('is-panning');
    pan.scroller.setPointerCapture?.(event.pointerId);
    window.getSelection()?.removeAllRanges();
  }
  pan.scroller.scrollLeft = pan.left - dx;
  pan.scroller.scrollTop = pan.top - dy;
});

function endPan(event) {
  if (!pan || event.pointerId !== pan.pointerId) return;
  if (pan.dragging) {
    pan.scroller.classList.remove('is-panning');
    // Swallow the click this release fires, before Elm sees it. A release outside the window fires no
    // click, so the listener goes once this event has run its course rather than catching a later one.
    const swallow = (click) => {
      click.stopPropagation();
      click.preventDefault();
    };
    window.addEventListener('click', swallow, { capture: true, once: true });
    setTimeout(
      () => window.removeEventListener('click', swallow, { capture: true }),
      0,
    );
  }
  pan = null;
}
document.addEventListener('pointerup', endPan);
document.addEventListener('pointercancel', endPan);

// Week navigation changes the URL so it can be bookmarked and the back button works.
app.ports.pushUrl.subscribe((url) => history.pushState({}, '', url));
window.addEventListener('popstate', () =>
  app.ports.onUrlChange.send(window.location.pathname),
);

// Unpoly (loaded on every page) would otherwise re-render the page when Back returns to the
// first week visited, which removes the editor. The popstate listener above handles it instead.
window.up?.on('up:location:restore', (event) => event.preventDefault());
