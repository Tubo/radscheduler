import { Calendar } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import listPlugin from '@fullcalendar/list';
import bootstrap5Plugin from '@fullcalendar/bootstrap5';
import nzLocale from '@fullcalendar/core/locales/en-nz';
import "../css/roster_calendar.css"

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
    eventSources: [
        "/api/calendar/shifts",
        { url: "/api/calendar/leaves", textColor: "black", backgroundColor: "DarkSeaGreen" },
        { url: "/api/calendar/holidays", display: "background" }
    ],
    eventDataTransform: function (eventData) {
        if (eventData.event_type === 'shift') {
            switch (eventData.title.split(":")[0]) {
                case "LONG":
                    eventData.textColor = "black"
                    eventData.backgroundColor = "#FFB6C1"
                    break
                case "NIGHT":
                    eventData.textColor = null
                    eventData.backgroundColor = "#000000"
                    break
                default:
                    eventData.textColor = "black"
                    eventData.backgroundColor = "PaleTurquoise"
            }
        }

        else if (eventData.event_type === 'leave' && eventData.title.includes("TBC")) {
            eventData.textColor = "white"
            eventData.backgroundColor = "grey"
        }

        eventData.extendedProps = eventData.extendedProps || {};
        eventData.extendedProps.initialBackgroundColor = eventData.backgroundColor;
        eventData.extendedProps.event_type = eventData.event_type;
        return eventData;
    },
    eventOrder: ["-event_type", "title"],
    locale: nzLocale,
    height: "90vh",
    rerenderDelay: 125,
    eventMouseEnter: function (info) {
        let eventTitle = info.event.title;
        let events = calendar.getEvents();
        events.forEach(event => {
            if (event.extendedProps.event_type !== "holiday" && event.title === eventTitle) {
                event.setProp('backgroundColor', '#FFC300');
            }
        });
    },
    eventMouseLeave: function (info) {
        let eventTitle = info.event.title;
        let events = calendar.getEvents();
        events.forEach(event => {
            if (event.title === eventTitle) {
                event.setProp('backgroundColor', event.extendedProps.initialBackgroundColor || '');
            }
        });
    },
});

calendar.render();