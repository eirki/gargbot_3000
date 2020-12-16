"use strict";

import * as config from "./config.js"

export function redirectLogin(state) {
    let url = new URL("/login" + config.ext, location.href)
    url.searchParams.set("state", state)
    location.href = url;
}

export function getToken() {
    const token = localStorage.getItem('garglingtoken');
    return token
}

export function getBackend(token, endpoint, params) {
    const url = new URL(endpoint, config.backend_url)
    url.search = new URLSearchParams(params).toString();
    console.log(`Fetching ${url}`)
    return fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': 'Bearer ' + token
        }
    })
        .then(response => {
            if (response.status === 401) {
                redirectLogin();
            }
            return response
        })
        .then(response => {
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                return response.json()
            } else {
                return response
            }
        });
}

export function postBackend(token, endpoint, data) {
    const url = new URL(endpoint, config.backend_url)
    console.log(`Fetching ${url}`)
    return fetch(url, {
        method: 'POST',
        headers: {
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
        .then(response => {
            if (response.status === 401) {
                redirectLogin();
            }
            return response
        })
}
