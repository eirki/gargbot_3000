"use strict";

import * as config from "./config.js"

function main() {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString)
    const code = urlParams.get("code")
    const state = urlParams.get("state")
    const url = new URL("/auth", config.backend_url)
    console.log(url)
    url.searchParams.set('code', code);
    fetch(url, {
        headers: {
            'Content-Type': 'application/json'
        },
    })
        .then(result => result.json())
        .then(data => {
            console.log(data)
            let token = data["access_token"]
            console.log(token)
            window.localStorage.setItem('garglingtoken', token)
            let url = new URL("/" + state + config.ext, location.href)
            location.href = url
        })
        .catch(error => {
            let elem = document.getElementById("msg");
            elem.innerHTML = "Could not authenticate";

        })

}


main()
