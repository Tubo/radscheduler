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
    const tooltip = bootstrap.Tooltip.getOrCreateInstance(element);
    // dispose the tooltip when the anchor element is removed
    up.destructor(element, () => {
        tooltip.dispose()
    })
})

up.compiler(".event-leave-button", { batch: true }, function (elements, data) {
    // On page load, we need to count the number of leaves for that column
    // and update the footer cell with the total number of leaves.

    const grouped_by_date = data.reduce((acc, item) => {
        // group each item in data by date
        const date = item.date;
        if (!acc[date]) {
            acc[date] = [];
        }
        acc[date].push(item);
        return acc;
    }, {});

    // iterate over each date and update the footer cell
    for (const date in grouped_by_date) {
        const leaves = grouped_by_date[date].filter(item => item.eventCancelled === "False");
        const total_leaves = leaves.length;
        const approved_leaves = leaves.filter(item => item.eventApproved === "True").length;
        const pending_leaves = leaves.filter(item => item.eventPending === "True").length;
        const footer_cell = up.fragment.get(`tfoot th[data-date='${date}']`);
        up.fragment.get(footer_cell, '.total-leaves').textContent = total_leaves;
        up.fragment.get(footer_cell, '.approved-leaves').textContent = approved_leaves;
        up.fragment.get(footer_cell, '.pending-leaves').textContent = pending_leaves;
    }
})

up.on('up:form:submit', (event, form) => {
    // Get the closest dropdown menu and hide it when the user clicks a link.
    const dd = up.fragment.closest(form, ".dropdown-menu")
    // if dd is null, then the form is not inside a dropdown menu
    if (!dd) {
        return
    }
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

