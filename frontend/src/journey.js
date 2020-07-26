"use strict";

import { getToken, redirectLogin } from "./common.js"
import * as config from "./config.js"


function generateTableHead(table, data) {
    let thead = table.createTHead();
    let row = thead.insertRow();
    for (let key in data) {
        let th = document.createElement("th");
        let text = document.createTextNode(key);
        th.appendChild(text);
        row.appendChild(th);
    }
    for (let key of ["start", "stop", "delete"]) {
        let th = document.createElement("th");
        let text = document.createTextNode("");
        th.appendChild(text);
        row.appendChild(th);

    }
}

function generateTable(table, data, token) {
    for (let element of data) {
        let row = table.insertRow();
        for (let key in element) {
            let cell = row.insertCell();
            let text = document.createTextNode(element[key]);
            cell.appendChild(text);
        }
        let id = element["id"]
        for (let key of ["start", "stop", "delete"]) {
            let cell = row.insertCell();
            let btn = document.createElement("button")
            btn.innerHTML = key
            btn.addEventListener("click", function () {
                const url = new URL(`/${key}_journey?journey_id=${id}`, config.backend_url)
                return fetch(url, {
                    headers: {
                        'Authorization': 'Bearer ' + token
                    }
                }).then(response => {
                    listJourneys(token)
                })
            });
            cell.appendChild(btn);

        }
    }
}

async function listJourneys(token) {
    let table = document.querySelector("table");
    if (table.hasChildNodes()) {
        table.innerHTML = '';

    }
    const url = new URL('/list_journeys', config.backend_url)
    console.log(`Fetching ${url}`)
    return fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': 'Bearer ' + token
        }
    })
        .then(response => {
            return response.json();
        })
        .then(data => {
            let journeys = data["journeys"];
            let first = journeys[0]
            generateTableHead(table, first);
            generateTable(table, journeys, token);
        })
}

function addUploadButton() {
    let header = document.createElement("h3");
    header.innerHTML = "New journey"
    document.body.appendChild(header);

    let form = document.createElement("form");

    let file = document.createElement("input");
    file.setAttribute("type", "file");
    file.setAttribute("required", true);
    file.setAttribute("accept", ".gpx");
    file.setAttribute("name", "uploadFile");
    form.appendChild(file);
    form.appendChild(document.createElement("br"))
    form.appendChild(document.createElement("br"))

    let label = document.createElement("label");
    label.innerHTML = "Origin"
    form.appendChild(label);
    form.appendChild(document.createElement("br"))

    let origin = document.createElement("input");
    origin.setAttribute("type", "text");
    origin.setAttribute("required", true);
    origin.setAttribute("name", "origin");
    form.appendChild(origin);
    form.appendChild(document.createElement("br"))
    form.appendChild(document.createElement("br"))

    let label2 = document.createElement("label");
    label2.innerHTML = "Destination"
    form.appendChild(label2);
    form.appendChild(document.createElement("br"))

    let dest = document.createElement("input");
    dest.setAttribute("type", "text");
    dest.setAttribute("required", true);
    dest.setAttribute("name", "dest");
    form.appendChild(dest);
    form.appendChild(document.createElement("br"))
    form.appendChild(document.createElement("br"))

    let submit = document.createElement("input");
    submit.setAttribute("type", "submit");
    form.appendChild(submit);

    form.addEventListener('submit', submitForm)

    document.body.appendChild(form);

}


async function submitForm(e) {
    e.preventDefault()
    let file = e.target.uploadFile.files[0]
    let origin = e.target.origin.value
    let dest = e.target.dest.value
    let formData = new FormData();
    formData.append('file', file)
    formData.append('origin', origin)
    formData.append('dest', dest)
    const upload_url = new URL("/upload_journey", config.backend_url)
    let token = getToken();
    return fetch(upload_url, {
        method: 'POST',
        body: formData,
        headers: {
            'Authorization': 'Bearer ' + token,
        },

    }).then(response => {
        listJourneys(token)
    })
}



async function main() {
    let token = getToken();
    if (!token) {
        redirectLogin("journey")
    }
    await listJourneys(token)
    addUploadButton()
}


main()
