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
