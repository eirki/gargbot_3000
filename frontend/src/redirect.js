"use strict";

function main() {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString)
    const code = urlParams.get("code")
    const state = urlParams.get("state")
    const url = new URL("/auth", process.env.backend_url)
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
            location.href = state
        })
        .catch(error => {
            let elem = document.getElementById("msg");
            elem.innerHTML = "Could not authenticate";

        })

}


main()
