"use strict";

import h from 'hyperscript'
import 'bootstrap/dist/css/bootstrap.min.css';

import { getToken, redirectLogin, getBackend, postBackend } from "./utils.js"



let errormsg = "Errår. Kan det va fel på systemet?"

function toggleService(elem, service_name, measure, token, all_buttons) {
    let otherEnabled = all_buttons.filter(btn => !btn.disabled && btn !== elem)
    let wasChecked = null
    for (let box of otherEnabled) {
        box.disabled = true;
        if (box.checked) {
            wasChecked = box
        }
    }
    let checked = elem.checked
    elem.disabled = true

    let data = {
        'service': service_name,
        'measure': measure,
        'enable': checked
    }
    postBackend(token, "/health_toggle", data).then(response => {
        if (response.status !== 200) {
            throw ("Failed to set setting:" + response.status);
        }
    })
        .catch(error => {
            console.log(error)
            elem.checked = !checked
            if (wasChecked) {
                wasChecked.checked
            }
            window.alert(errormsg)
        })
        .finally(() => {
            for (let box of otherEnabled) {
                box.checked = false;
                box.disabled = false
            }
            elem.disabled = false
        })
}


function redirectService(url) {
    location.href = url
}


function authorizeService(elem, service, token) {
    getBackend(token, `/${service}/auth`)
        .then(data => redirectService(data["auth_url"]))
        .catch(error => {
            console.log(error)
            window.alert(errormsg)
        })
}


function userHealthData(token) {
    return getBackend(token, "/health_status")
}


function activity_button(activity, service_id, service_data, token, all_buttons) {
    let button = h("input.form-check-input", {
        type: "checkbox",
        disabled: !service_data || (activity === "weight" && service_id !== "fitbit"),
        checked: service_data ? service_data[`enable_${activity}`] : false,
        onchange: event => toggleService(event.target, service_id, activity, token, all_buttons)
    })
    all_buttons.push(button)
    return button
}


async function renderTable(token) {
    let services = [
        { name: 'Fitbit', id: 'fitbit' },
        { name: 'Polar', id: 'polar' },
        { name: 'Google Fit', id: 'googlefit' },
        { name: 'Withings', id: 'withings' },
    ]
    let step_buttons = []
    let weight_buttons = []

    let user_data = await userHealthData(token).then(obj => obj["data"])
    return h("table.table", [
        h("thead",
            h("tr", ["service", "steps", "weight & fat", ""].map(header => h("th", header)))),
        h("tbody", services.map(service => {
            let service_data = user_data[service["id"]]
            return h("tr", [
                h("td", service["name"]),
                h("td", [
                    h("div.form-check.form-switch", [
                        activity_button("steps", service["id"], service_data, token, step_buttons)
                    ])]),
                h("td", [
                    h("div.form-check.form-switch", [
                        activity_button("weight", service["id"], service_data, token, weight_buttons)
                    ])]),
                h("td", [
                    h("input.btn.btn-outline-primary.btn-sm", {
                        type: "button",
                        value: !service_data ? "Authenticate" : "Reauthenticate",
                        onclick: event => authorizeService(event.target, service["id"], token)
                    })]),
            ])
        }))

    ])
}


async function main() {
    let token = getToken();
    if (!token) {
        redirectLogin("health")
    }
    var root = document.body
    root.appendChild(await renderTable(token))

}


main();
