import '../sass/project.scss';

import 'htmx.org'
window.htmx = require('htmx.org');

console.log("initializing tooltips")
const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))
console.log("initialized tooltips")
