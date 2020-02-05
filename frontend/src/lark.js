"use strict";

import countdown from "countdown";

console.log(countdown);

function setBackground() {
    const base_url = process.env.api_url
    let args = process.env.countdown_args;
    args = args.split(" ")
    args = args.join(",")
    let url = base_url + "/" + args
    fetch(url, {
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


function startTimer() {
    const message = document.getElementById("message");
    const display = document.getElementById("time");
    const until_date = new Date(Number(process.env.countdown_date));
    console.log(until_date)
    const countdown_message = process.env.countdown_message;
    const ongoing_message = process.env.ongoing_message;
    const finished_message = process.env.finished_message;

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


// setBackground()
startTimer();
