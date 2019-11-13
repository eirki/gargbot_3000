"use strict";

function setBackground() {
    const base_url = process.env.api_url
    let args = process.env.countdown_args;
    args = args.split(" ")
    args = args.join(",")
    let url = base_url + "/" + args
    let image_url = fetch(url, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        },
    })
        .then(response => {
            if (response.status !== 200) {
                console.log("Fetch problem. Status Code:", response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log(data)
            let image_url = data["url"];
            document.body.style.background = `url(${image_url}) no-repeat center center`;
        })
        .catch(err => console.log('Fetch Error', err));
}

setBackground()
