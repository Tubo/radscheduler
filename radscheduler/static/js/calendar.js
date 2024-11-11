import { Calendar } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import listPlugin from '@fullcalendar/list';
import bootstrap5Plugin from '@fullcalendar/bootstrap5';
import nzLocale from '@fullcalendar/core/locales/en-nz';

const calendarEl = document.getElementById('calendar');

let calendar = new Calendar(calendarEl, {
    plugins: [dayGridPlugin, listPlugin, bootstrap5Plugin],
    initialView: window.innerWidth > 768 ? 'dayGridMonth' : 'listWeek',
    windowResize: function (view) {
        // If the window is resized to a width greater than 768px, change the view to dayGridMonth
        if (window.innerWidth > 768) {
            calendar.changeView('dayGridMonth');
        } else {
            calendar.changeView('listWeek');
        }
    },
    themeSystem: 'bootstrap5',
    events: "/api/calendar/events/",
    eventDataTransform: function (eventData) {
        eventData.extendedProps = eventData.extendedProps || {};
        eventData.extendedProps.initialBackgroundColor = eventData.backgroundColor;
        eventData.extendedProps.initialBorderColor = eventData.borderColor;
        return eventData;
    },
    locale: nzLocale,
    height: "90vh",
    eventOrder: "order,title",
    eventMouseEnter: function (info) {
        let eventTitle = info.event.title;
        let events = calendar.getEvents();
        events.forEach(event => {
            if (event.title === eventTitle) {
                event.setProp('backgroundColor', 'yellow');
                event.setProp('borderColor', 'yellow');
            }
        });
    },
    eventMouseLeave: function (info) {
        let eventTitle = info.event.title;
        let events = calendar.getEvents();
        events.forEach(event => {
            if (event.title === eventTitle) {
                event.setProp('backgroundColor', event.extendedProps.initialBackgroundColor || '');
                event.setProp('borderColor', event.extendedProps.initialBorderColor || '');
            }
        });
    },
});

calendar.render();