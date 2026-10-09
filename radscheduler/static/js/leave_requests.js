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

Elm.LeaveRequests.init({
  node: document.getElementById('leave-requests-app'),
  flags: JSON.parse(
    document.getElementById('leave-requests-flags').textContent,
  ),
});
