import { Elm } from '../elm/Editor.elm';

const node = document.getElementById('editor-app');
const flags = JSON.parse(document.getElementById('editor-flags').textContent);
const app = Elm.Editor.init({ node, flags });

// Week navigation changes the URL so it can be bookmarked and the back button works.
app.ports.pushUrl.subscribe((url) => history.pushState({}, '', url));
window.addEventListener('popstate', () =>
  app.ports.onUrlChange.send(window.location.pathname),
);

// Unpoly (loaded on every page) would otherwise re-render the page when Back returns to the
// first week visited, which removes the editor. The popstate listener above handles it instead.
window.up?.on('up:location:restore', (event) => event.preventDefault());
