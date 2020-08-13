"use strict";


import { getToken, redirectLogin } from "./common.js"
import * as config from "./config.js"


function parseService() {
    let pathname = window.location.pathname;
    let service = pathname.replace(config.ext, "").substring(1);
    return service
}

function getCodeifRedirected() {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString)
    const code = urlParams.get("code")
    console.log(code)
    const state = urlParams.get("state")
    console.log(state)
    return [code, state]
}

function forwardServiceCode(service, slackToken, code, state) {
    const url = new URL(`/${service}/redirect`, config.backend_url)
    url.searchParams.set('code', code);
    url.searchParams.set('state', state);
    return fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': 'Bearer ' + slackToken
        }
    })
        .then(response => {
            if (response.status !== 200) {
                throw `Failed to authenticate:${response.status}`;
            }
        })
        .catch(err => {
            console.log('Fetch Error', err)
            let elem = document.getElementById("msg");
            elem.innerHTML = `error sending ${service} Code to gargbot`
        });

}


function authorizeService(service, token) {
    const url = new URL(`/${service}/auth`, config.backend_url)
    return fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': 'Bearer ' + token
        }
    })
        .then(response => {
            if (response.status !== 200) {
                throw "Failed to authenticate"
            }
            return response
        })
        .then(response => {
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                return response.json()
            }
        })
        .then(data => {
            console.log(data);
            return data
        })
        .catch(err => console.log('Fetch Error', err));

}

function redirectService(url) {
    location.href = url
}


function renderHealthMenu(service, token, report_enabled) {
    let elem = document.getElementById("msg");
    elem.innerHTML = "enable report?";
    let toggle = document.createElement("label");
    toggle.className = 'switch'

    let input = document.createElement("input");
    input.type = "checkbox";
    toggle.appendChild(input)

    let span = document.createElement("span");
    span.className = 'slider'
    toggle.appendChild(span)

    input.onclick = buttonClickMaker(service, token);
    input.checked = report_enabled;
    document.body.appendChild(toggle);

}

function toggleReport(service, token, enable) {
    const url = new URL("/toggle_report", config.backend_url)
    let data = {
        'service': service,
        'enable': enable
    }
    return fetch(url, {
        method: 'POST',
        headers: {
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
        .then(response => {
            if (response.status !== 200) {
                throw ("Failed to set setting:" + response.status);
            }
            console.log(response)
        })
}

function buttonClickMaker(service, token) {
    async function inner() {
        this.disabled = true;
        let checked = this.checked
        try {
            await toggleReport(service, token, checked)
        } catch {
            console.log(checked)
            this.checked = !checked
        } finally {
            this.disabled = false;
        }
    }
    return inner
}
async function main() {
    let service = parseService();
    let slackToken = getToken();
    if (!slackToken) {
        // not logged in to slack
        redirectLogin(service)
    }

    let [serviceCode, state] = getCodeifRedirected();
    if (serviceCode != null) {
        // in the process of logging in to service
        await forwardServiceCode(service, slackToken, serviceCode, state)
    }

    let user_data = await authorizeService(service, slackToken)
    if (user_data && "auth_url" in user_data) {
        redirectService(user_data["auth_url"])
    } else if (user_data && "report_enabled" in user_data) {
        console.log(`server indicates logged into ${service}`)
        let report_enabled = user_data["report_enabled"]
        renderHealthMenu(service, slackToken, report_enabled);
    } else {
        let elem = document.getElementById("msg");
        elem.innerHTML = "Failed to authenticate";
    }

}


main();

