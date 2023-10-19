import { Calendar } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import 'bootstrap-icons/font/bootstrap-icons.css';
import bootstrap5Plugin from '@fullcalendar/bootstrap5';
import nzLocale from '@fullcalendar/core/locales/en-nz';

const calendarEl = document.getElementById('calendar');

let calendar = new Calendar(calendarEl, {
    plugins: [dayGridPlugin, bootstrap5Plugin],
    initialView: 'dayGridMonth',
    themeSystem: 'bootstrap5',
    events: "/calendar/events/",
    locale: nzLocale,
    height: "90vh"
});



calendar.render();