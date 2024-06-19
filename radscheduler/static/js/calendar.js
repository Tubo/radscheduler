import { Calendar } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import listPlugin from '@fullcalendar/list';
import bootstrap5Plugin from '@fullcalendar/bootstrap5';
import nzLocale from '@fullcalendar/core/locales/en-nz';

const calendarEl = document.getElementById('calendar');

let calendar = new Calendar(calendarEl, {
    plugins: [dayGridPlugin, listPlugin, bootstrap5Plugin],
    initialView: window.innerWidth > 768 ? 'dayGridMonth' : 'listWeek',
    themeSystem: 'bootstrap5',
    events: "/api/calendar/events/",
    locale: nzLocale,
    height: "90vh",
    eventOrder: "order,title",
});

calendar.render();