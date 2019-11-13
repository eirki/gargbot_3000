"use strict";

import countdown from "countdown";

function startTimer() {
    const message = document.getElementById("message");
    const display = document.getElementById("time");
    const until_date = new Date(Number(process.env.countdown_date));
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

startTimer();
