import '@popperjs/core';
import * as bootstrap from 'bootstrap'
import 'bootstrap-icons/font/bootstrap-icons.css';

const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))