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

// Week navigation changes the URL so it can be bookmarked and the back button works.
app.ports.pushUrl.subscribe((url) => history.pushState({}, '', url));
window.addEventListener('popstate', () =>
  app.ports.onUrlChange.send(window.location.pathname),
);

// Unpoly (loaded on every page) would otherwise re-render the page when Back returns to the
// first week visited, which removes the editor. The popstate listener above handles it instead.
window.up?.on('up:location:restore', (event) => event.preventDefault());
