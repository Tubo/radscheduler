import Alpine from 'alpinejs'
import { TabulatorFull as Tabulator } from 'tabulator-tables';
const { DateTime, Interval } = require("luxon");

// import "tabulator-tables/dist/css/tabulator.min.css"
import "tabulator-tables/dist/css/tabulator_bootstrap5.min.css"
import "../css/roster_table.scss"

window.Alpine = Alpine
window.table = rosterTable('#roster-table')

Alpine.store('state', {
    start: DateTime.now().minus({ days: 14 }).toISODate(),
    end: DateTime.now().plus({ months: 3 }).toISODate(),
    tableData: null, // set by rosterTable.ajaxResponse
    refresh: function () {
        window.table.clearData();
        window.table.setData()
    }
})

Alpine.start()

function rosterTable(id) {
    return new Tabulator(id, {
        layout: 'fitDataFill',
        height: "80vh",
        ajaxURL: '/api/table/events/',
        ajaxContentType: 'json',
        ajaxParams: () => ({ start: Alpine.store("state").start, end: Alpine.store("state").end }),
        ajaxResponse: function (url, params, response) {
            Alpine.store('state').tableData = response
            return response.table
        },
        headerSort: false,
        autoColumns: true,
        autoColumnsDefinitions: function (definitions) {
            const registrars = Alpine.store('state').tableData.columns
            const years = [...new Set(registrars.map(item => item.year))].sort().reverse();
            let result = [];

            result.push({
                field: 'date',
                title: 'Date',
                frozen: true,
                minWidth: 200,
                maxWidth: 200,
                hozAlign: 'left',
                formatter: function (cell, formatterParams, onRendered) {
                    const el = cell.getElement()
                    const value = cell.getValue()
                    const row = cell.getRow().getElement()
                    const holiday = cell.getData().holiday

                    el.style.fontFamily = 'monospace'
                    // Saturday and Sunday column background colour
                    const date = DateTime.fromISO(value)
                    let content = date.toFormat('dd/MM/yy ccc');

                    if (holiday !== "") {
                        content += " <small>🎉</small>"
                    }
                    return content
                },

                tooltip: function (e, cell, onRendered) {
                    //e - mouseover event
                    //cell - cell component
                    //onRendered - onRendered callback registration function
                    const holiday = cell.getData().holiday

                    if (holiday !== "") {
                        var tip = document.createElement("div");
                        tip.innerHTML = holiday
                        return tip;
                    }
                },
            })

            const sorted_registrars = registrars.sort(function (a, b) {
                return b.year - a.year || a.username.localeCompare(b.username)
            });

            years.forEach((year) => {
                result.push({
                    title: "Year " + year,
                    columns: sorted_registrars.filter((registrar) => registrar.year === year).map((registrar) => {
                        return {
                            field: registrar.id.toString(),
                            title: registrar.username,
                            formatter: function (cell, formatterParams, onRendered) {
                                const el = cell.getElement()
                                const value = cell.getValue()
                                const date = cell.getData().date
                                const reg_id = cell.getField()
                                const shifts = Alpine.store('state').tableData.shifts
                                const leaves = Alpine.store('state').tableData.leaves
                                const statuses = Alpine.store('state').tableData.statuses
                                let content = ""

                                if (typeof value === 'string' && value.includes(':')) {
                                    const cellType = value.split(':')[0]
                                    id = value.split(':')[1]

                                    if (cellType === 'leave') {
                                        el.style.backgroundColor = 'rgba(144, 238, 144, 0.53)'
                                        let leave = leaves[id]
                                        content = leave.type

                                        if (leave.portion !== "ALL") {
                                            content = content + " <u>" + leave.portion + "</u>"
                                        }

                                    } else if (cellType === 'shift') {
                                        el.style.backgroundColor = 'rgba(249, 7, 2, 0.5)'
                                        el.style.fontWeight = 'bold'
                                        const shift = shifts[id]
                                        content = shift.type

                                        if (shift.extra_duty) {
                                            el.style.backgroundColor = '#e8e17a'
                                            content += " 💵"
                                        }

                                        if (shift.type === "Sleep day") {
                                            el.style.backgroundColor = 'inherit'
                                            content = "💤"
                                        } else if (shift.type === "RDO") {
                                            el.style.backgroundColor = 'inherit'
                                            content = "🏡"
                                        }
                                    }
                                } else {
                                    content = ""
                                }

                                const relevantStatus = statuses.filter((status) => {
                                    const start = DateTime.fromISO(status.start)
                                    const end = DateTime.fromISO(status.end)
                                    const thisDate = DateTime.fromISO(date)
                                    const weekdays = status.weekdays
                                    const thisWeekday = thisDate.toFormat('c') - 1
                                    const interval = Interval.fromDateTimes(start, end)
                                    return interval.contains(thisDate)
                                        && status.registrar === parseInt(reg_id)
                                        && (weekdays.includes(thisWeekday) || weekdays.length === 0)
                                })

                                if (relevantStatus.length > 0) {
                                    relevantStatus.map((status) => status.type).forEach((statusType) => {
                                        if (statusType === "Reliever") {
                                            if (content === "") {
                                                content += " <small>🛟</small>"
                                            }
                                        } else if (statusType === "Buddy required") {
                                            if (content === "Long day") {
                                                content += " <small>🤝</small>"
                                            }
                                        } else if (statusType === "Not available") {
                                            el.style.backgroundColor = '#808080b0'
                                            content += " <small>N/A</small>"
                                        } else if (statusType === "Pre-oncall") {
                                            if (content === "") {
                                                content += " <small>👶</small>"
                                            }
                                        }
                                        else {
                                            content += "*"
                                        }
                                    })
                                }
                                return content
                            },

                            tooltip: function (e, cell, onRendered) {
                                //e - mouseover event
                                //cell - cell component
                                //onRendered - onRendered callback registration function
                                const date = cell.getData().date
                                const reg_id = cell.getField()
                                const statuses = Alpine.store('state').tableData.statuses

                                const relevantStatus = statuses.filter((status) => {
                                    const start = DateTime.fromISO(status.start)
                                    const end = DateTime.fromISO(status.end)
                                    const thisDate = DateTime.fromISO(date)
                                    const weekdays = status.weekdays
                                    const thisWeekday = thisDate.toFormat('c') - 1
                                    const interval = Interval.fromDateTimes(start, end)
                                    return interval.contains(thisDate)
                                        && status.registrar === parseInt(reg_id)
                                        && (weekdays.includes(thisWeekday) || weekdays.length === 0)
                                })
                                if (relevantStatus.length > 0) {
                                    const tip = document.createElement("div");
                                    relevantStatus.forEach((status) => {
                                        var statusDiv = document.createElement("p");
                                        statusDiv.innerHTML = status.type
                                        tip.appendChild(statusDiv)
                                    })
                                    return tip;
                                }
                            },
                        }
                    })
                })
            })
            return result;
        },
        columnDefaults: {
            hozAlign: 'center',
            headerSort: false,
            resizable: false,
            minWidth: 80,
            maxWidth: 100,
            headerHozAlign: 'center',
        },
        rowFormatter: function (row) {
            //row - row component
            const data = row.getData();
            const el = row.getElement();

            let date = DateTime.fromISO(data.date)

            if (date.weekday === 6 || date.weekday === 7) {
                if (el.classList.contains('tabulator-row-even')) {
                    el.style.backgroundColor = '#b1b1b1'
                } else if (el.classList.contains('tabulator-row-odd')) {
                    el.style.backgroundColor = '#c6c6c6'
                }
            }

            if (date.toISODate() === DateTime.now().toISODate()) {
                el.style.border = 'solid black'
                el.style.borderWidth = '4px 0'
            }
        },
    })
}
