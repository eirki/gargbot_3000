"use strict";


import { getToken, redirectLogin, getBackend, postBackend } from "./utils.js"


let errormsg = "Errår. Kan det va fel på systemet?"

function toggleService(elem, service_name, measure, token) {
    let otherEnabled = document.querySelectorAll(`tr:not(#${service_name}) > th > .switch > .${measure}:not([disabled])`)
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

function activateTable(user_data, token) {
    let service_rows = document.querySelectorAll(".service-row")
    for (let row of service_rows) {
        let service_name = row.id
        let service_data = user_data[service_name]

        let steps_input = row.querySelector(".steps")
        steps_input.addEventListener("change", (event) => toggleService(event.target, service_name, "steps", token))

        let weight_input = row.querySelector(".weight")
        weight_input.addEventListener("change", (event) => toggleService(event.target, service_name, "weight", token))

        let auth_input = row.querySelector(".auth")
        auth_input.addEventListener("click", (event) => authorizeService(event.target, service_name, token))
        auth_input.disabled = false
        if (service_data) {
            auth_input.value = "Reauthenticate"
        } else {
            continue
        }

        steps_input.disabled = false
        steps_input.checked = service_data["enable_steps"]

        if (service_name === "fitbit") {
            weight_input.disabled = false
        }
        weight_input.checked = service_data["enable_weight"]
    }
}


function userHealthData(token) {
    return getBackend(token, "/health_status")
}

async function main() {
    let token = getToken();
    if (!token) {
        redirectLogin("health")
    }

    let user_data = await userHealthData(token).then(obj => obj["data"])
    activateTable(user_data, token);

}


main();

