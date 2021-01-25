"use strict";

import h from 'hyperscript'
import 'bootstrap/dist/css/bootstrap.min.css';

import { getBackend, getToken, redirectLogin } from "./utils.js"
import * as config from "./config.js"


async function startStop(action, journey_id, token) {
    await getBackend(token, `/${action}_journey`, { journey_id: journey_id }).then(() => listJourneys(token))
}


async function journeyList(token) {
    let keys = ["journey_id", "destination", "origin", "started_at", "finished_at", "n_waypoints", "distance", "ongoing"]
    return await getBackend(token, "/list_journeys")
        .then(data => data["journeys"])
        .then(journeys => [
            h("h3", "Journeys"),
            h("table.table", [
                h("thead",
                    [h("tr",
                        [keys.map(header => h("th", header)),
                        h("th", ""),
                        h("th", "")])]),
                h("tbody", journeys.map(journey => h(
                    "tr",
                    keys.map(key => h("td", journey[key])),
                    h("td", [h("button.btn.btn-primary", { type: "button" }, "start", { onclick: (() => startStop("start", journey['id'], token)) })]),
                    h("td", h("button.btn.btn-warning", { type: "button" }, "stop", { onclick: (() => startStop("stop", journey['id'], token)) })),
                )))
            ])]
        )
}

function uploadForm(token) {
    return [
        h("h3", "New journey"),
        h("form", { onsubmit: async e => await submitForm(e, token) }, [
            h("br"),
            h("div.mb-3", [
                h("input.form-control", {
                    type: "file",
                    required: true,
                    accept: ".gpx",
                    name: "uploadFile",
                })
            ]),
            h("div.mb-3.row", [
                h("label.col-sm-2.col-form-label",
                    { htmlFor: "originName" },
                    "Origin"
                ),
                h("div.col-sm-10", [
                    h("input.form-control", {
                        id: "originName",
                        type: "text",
                        required: true,
                        name: "origin",
                    })]),
            ]),
            h("div.mb-3.row", [
                h("label.col-sm-2.col-form-label",
                    { htmlFor: "destName" },
                    "Dest"
                ),
                h("div.col-sm-10", [
                    h("input.form-control", {
                        id: "destName",
                        type: "text",
                        required: true,
                        name: "dest",
                    })]),
            ]),
            h("input.btn.btn-primary", {
                type: "submit",
            })
        ])
    ]
}


async function submitForm(e, token) {
    e.preventDefault()
    let file = e.target["uploadFile"].files[0]
    let origin = e.target["origin"].value
    let dest = e.target["dest"].value
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
        h("button.btn.btn-primary", "Run update", {
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
    root.appendChild(h("div.ms-3", [
        await journeyList(token),
        h("br"),
        uploadForm(token),
        h("br"),
        updateButton(token)
    ]))
}


main()
