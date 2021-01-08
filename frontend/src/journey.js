"use strict";

import h from 'hyperscript'

import { getBackend, getToken, redirectLogin } from "./utils.js"
import * as config from "./config.js"


async function startStop(action, journey_id, token) {
    await getBackend(token, `/${action}_journey`, { journey_id: journey_id }).then(() => listJourneys(token))
}


async function journeyList(token) {
    return await getBackend(token, "/list_journeys")
        .then(data => data["journeys"])
        .then(journeys => [
            h("h3", "Journeys"),
            h("table", [
                h("tr",
                    Object.keys(journeys[0]).map(header => h("th", header))),
                journeys.map(journey => h(
                    "tr",
                    Object.values(journey).map(val => h("td", val)),
                    h("td", h("button", "start", { onclick: (() => startStop("start", journey['id'], token)) })),
                    h("td", h("button", "stop", { onclick: (() => startStop("stop", journey['id'], token)) })),
                ))
            ])]
        )
}

function uploadForm() {
    return [
        h("h3", "New journey"),
        h("form", { onsubmit: async e => await submitForm(e, token) }, [
            h("input", {
                type: "file",
                required: true,
                accept: ".gpx",
                name: "uploadFile",

            }),
            h("br"),
            h("br"),
            h("label", "Origin"),
            h("br"),
            h("input", {
                type: "text",
                required: true,
                name: "origin",
            }),
            h("br"),
            h("label", "Destination"),
            h("br"),
            h("input", {
                type: "text",
                required: true,
                name: "dest",
            }),
            h("br"),
            h("input", {
                type: "submit",
            })
        ])
    ]
}


async function submitForm(e, token) {
    e.preventDefault()
    let file = e.target.uploadFile.files[0]
    let origin = e.target.origin.value
    let dest = e.target.dest.value
    let formData = new FormData();
    formData.append('file', file)
    formData.append('origin', origin)
    formData.append('dest', dest)
    const upload_url = new URL("/upload_journey", config.backend_url)
    await fetch(upload_url, {
        method: 'POST',
        body: formData,
        headers: {
            'Authorization': 'Bearer ' + token,
        },

    })
}


function updateButton(token) {
    return [
        h("h3", "Ongoing journey"),
        h("button", "Run update", {
            onclick: (
                async () => await getBackend(token, "/run_journey_update")
                    .then(response => alert(response.status)))
        })
    ]
}



async function main() {
    let token = getToken();
    if (!token) {
        redirectLogin("journey")
    }
    var root = document.body
    root.appendChild(h("div", [
        await journeyList(token),
        uploadForm(token),
        updateButton(token)
    ]))
}


main()
