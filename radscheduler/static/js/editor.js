import "../css/editor.scss"

import Alpine from 'alpinejs'
import 'unpoly/unpoly.js'
import 'unpoly/unpoly.css'
import 'unpoly/unpoly-bootstrap5.js'
import 'unpoly/unpoly-bootstrap5.css'

window.Alpine = Alpine

up.compiler("#menu-bar", function (element) {
    up.context.shift_types = getCheckedValues(element, "shift_types");
    up.context.leave_types = getCheckedValues(element, "leave_types");

    console.log("up.context.shift_types:", up.context.shift_types);
    console.log("up.context.leave_types:", up.context.leave_types);

    function getCheckedValues(element, name) {
        return Array.from(element.querySelectorAll(`input[name='${name}']:checked`)).map(e => e.value);
    }
})

up.on("change", "input[name='shift_types'], input[name='leave_types']", function (event, element) {
    const contextKey = element.getAttribute('name');
    console.log("contextKey:", contextKey, "element.value:", element.value)

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