"use strict";

import countdown from "countdown";
import * as config from "./config.js"
import { getToken, redirectLogin } from "./common.js"


function setBackground(token) {
    let args = config.countdown_args;
    args = args.split(" ");
    args = args.join(",");
    const url = new URL(`/pic/${args}`, config.backend_url)
    console.log(`Fetching ${url}`)
    fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': 'Bearer ' + token
        }
    })
        .then(response => {
            if (response.status !== 200) {
                redirectLogin();
            }
            return response.json();
        })
        .then(data => {
            let image_url = data["url"];
            document.body.style.background = `url(${image_url}) no-repeat center center`;
        })
        .catch(err => console.log('Fetch Error', err));
}


function startTimer() {
    const message = document.getElementById("message");
    const display = document.getElementById("time");
    const until_date = config.countdown_date;
    console.log(until_date)
    const countdown_message = config.countdown_message;
    const ongoing_message = config.ongoing_message;
    const finished_message = config.finished_message;

    var refresh = setInterval(function () {
        var timespan_obj = countdown(until_date);
        var timespan_sentence = timespan_obj.toString();
        var timespan_sentence = timespan_sentence.replace(" and ", "<br>")
        var timespan_lines = timespan_sentence.split(", ").join("<br>");
        if (timespan_obj.value < 0) {
            display.innerHTML = timespan_lines;
            message.innerHTML = countdown_message;
        }
        else if (timespan_obj.value >= 0 && timespan_obj.value < 777600000) {
            display.innerHTML = timespan_lines;
            message.innerHTML = ongoing_message;
        }
        else {
            display.innerHTML = "";
            message.innerHTML = finished_message;
            clearInterval(refresh);  // exit refresh loop
        }
    }, 1000);
}

function main() {
    let token = getToken();
    if (!token) {
        redirectLogin("lark")
    }
    setBackground(token)
    startTimer()
}


main()
