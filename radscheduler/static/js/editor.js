import "../css/editor.scss"

up.compiler("#menu-bar", function (element) {
    up.context.shift_types = getCheckedValues(element, "shift_types");
    up.context.leave_types = getCheckedValues(element, "leave_types");

    console.log("up.context.shift_types:", up.context.shift_types);
    console.log("up.context.leave_types:", up.context.leave_types);

    function getCheckedValues(element, name) {
        return Array.from(element.querySelectorAll(`input[name='${name}']:checked`)).map(e => e.value);
    }
})

up.compiler("[data-bs-toggle='tooltip']", function (element) {
    // Initialize Bootstrap tooltips for the shift buttons after update.
    bootstrap.Tooltip.getOrCreateInstance(element);
    // new bootstrap.Tooltip(element);
})

up.on('up:form:submit', (event, form) => {
    // Get the closest dropdown menu and hide it when the user clicks a link.
    const dd = up.fragment.closest(form, ".dropdown-menu")
    // if dd is null, then the form is not inside a dropdown menu
    if (!dd) {
        return
    }
    console.log("form:", form, "dd:", dd)
    let dd_intance = bootstrap.Dropdown.getInstance(dd.previousElementSibling)
    dd_intance.hide()
})

up.on("change", "input[name='week_in_focus']", function (event, element) {
    // Update the context when the user changes the week in focus.
    const week_in_focus = element.value
    up.navigate({ url: "/roster/editor/" + week_in_focus })
})

up.on("change", "input[name='shift_types'], input[name='leave_types']", function (event, element) {
    // Update the context when the user checks or unchecks a shift type or leave type.
    const contextKey = element.getAttribute('name');

    if (!up.context[contextKey]) {
        up.context[contextKey] = [];
    }

    if (element.checked) {
        up.context[contextKey].push(element.value);
    } else {
        up.context[contextKey] = up.context[contextKey].filter(item => item !== element.value);
    }
    console.log("shift types:", up.context.shift_types)
    console.log("leave types:", up.context.leave_types)
})

up.on("shift:deleted", function (event) {
    // Destroy the shift element from the DOM when the server sends a 'shift:deleted' event.
    console.log("shift:deleted event:", event.shift_id)
    const el = document.querySelector(`[data-shift-id='${event.shift_id}']`)
    // remove tooltip instances
    el.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        bootstrap.Tooltip.getInstance(el).dispose();
    })
    up.destroy(el, { animate: 'fade-out' });
})

