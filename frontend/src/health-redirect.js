"use strict";


import { getToken, redirectLogin, getBackend } from "./utils.js"
import * as config from "./config.js"


function getServiceCode() {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString)
    const code = urlParams.get("code")
    const service = urlParams.get("service")
    return [service, code]
}


function forwardServiceCode(service, token, code) {
    return (
        getBackend(token, `/${service}/redirect`, { code: code })
            .then(response => {
                if (response.status !== 200) {
                    let elem = document.querySelector("#msg");
                    elem.innerHTML = `Error sending ${service} code to gargbot`
                    throw `Failed to authenticate:${response.status}`;
                }
            }))
}


function redirectToHealth() {
    let url = new URL("/health" + config.ext, location.href)
    location.href = url;
}


async function main() {
    let slackToken = getToken();
    if (!slackToken) {
        redirectLogin("health")
    }

    let [service, serviceCode] = getServiceCode();
    console.log(serviceCode)
    if (serviceCode != null) {
        // in the process of logging in to service
        forwardServiceCode(service, slackToken, serviceCode).then(redirectToHealth)
    }
}


main();
