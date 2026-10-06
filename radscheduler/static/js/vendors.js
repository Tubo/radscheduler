import 'unpoly/unpoly.css';
import 'unpoly/unpoly.js';
import 'unpoly/unpoly-bootstrap5.css';
import 'unpoly/unpoly-bootstrap5.js';

import '@popperjs/core';
import 'bootstrap-icons/font/bootstrap-icons.css';
import * as bootstrap from 'bootstrap';

import Alpine from 'alpinejs';

window.Alpine = Alpine;
window.bootstrap = bootstrap;

// Django reads the CSRF token from X-CSRFToken (Unpoly sends X-CSRF-Token by default).
up.protocol.config.csrfHeader = 'X-CSRFToken';
// Send DELETE etc. as-is rather than as a POST with a _method param, which Django ignores.
up.network.config.wrapMethod = false;
