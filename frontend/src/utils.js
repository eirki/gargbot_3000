"use strict";

import * as config from "./config.js"

export function redirectLogin(state) {
    let url = new URL("/login" + config.ext, location.href)
    url.searchParams.set("state", state)
    location.href = url;
}

export function getToken() {
    const token = localStorage.getItem('garglingtoken');
    console.log(`token: ${token}`)
    return token
}


export function fetchBackend(token, endpoint, params) {
    const url = new URL(endpoint, config.backend_url)
    url.search = new URLSearchParams(params).toString();
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
        });
}
