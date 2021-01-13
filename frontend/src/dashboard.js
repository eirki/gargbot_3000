"use strict";

import Highcharts from 'highcharts';
import more from 'highcharts/highcharts-more';
import Timeline from "highcharts/modules/timeline";

import { getToken, redirectLogin, getBackend } from "./utils.js"
import * as charts from "./charts"

more(Highcharts);
Timeline(Highcharts);



function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1 ')
}

function rgbToYIQ({ r, g, b }) {
    return ((r * 299) + (g * 587) + (b * 114)) / 1000;
}

function hexToRgb(hex) {
    if (!hex || hex === undefined || hex === '') {
        return undefined;
    }

    const result =
        /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);

    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : undefined;
}

function contrast(colorHex, threshold = 128) {
    if (colorHex === undefined) {
        return '#000';
    }

    const rgb = hexToRgb(colorHex);

    if (rgb === undefined) {
        return '#000';
    }

    return rgbToYIQ(rgb) >= threshold ? '#000' : '#fff';
}


function to_dict(data) {
    return Object.assign({}, ...data.map((x) => ({ [x.name]: x })));
}

async function distance_area_data(token) {
    return getBackend(token, "/dashboard/distance_area/1").then(resp => resp["data"])
}


function update_stats(leftSet, rightSet) {
    let parent = document.querySelector("#person_stats")
    let chldrn = parent.querySelectorAll(".statbox")
    for (let chld of chldrn) {
        let leftElem = chld.querySelector(".left")
        let leftVal = leftSet[chld.id]
        leftElem.innerHTML = formatNumber(leftVal)
        let rightElem = chld.querySelector(".right")
        let rightVal = rightSet[chld.id]
        rightElem.innerHTML = formatNumber(rightVal)
        let compElem = chld.querySelector(".comp")
        let compSign
        if (leftVal > rightVal) compSign = ">"
        else if (rightVal > leftVal) compSign = "<"
        else compSign = "="
        compElem.innerHTML = ` ${compSign} `

    }
}


async function personal_stats(token) {
    return getBackend(token, "/dashboard/personal_stats/1")
        .then(resp => {
            let as_list = resp["data"]
            let data = to_dict(as_list)

            let leftName = resp["name"]
            let rightName = "Average"

            let leftStats = data[leftName]
            let rightStats = data[rightName]

            let bothDatasets = [leftStats, rightStats]
            update_stats(...bothDatasets)

            let selectLeft = document.querySelector("#left_gargling")
            let selectRight = document.querySelector("#right_gargling")
            let names = Object.keys(data)
            names.sort()
            for (var name of names) {
                var opt = document.createElement('option');
                opt.value = name;
                opt.innerHTML = name;
                selectLeft.appendChild(opt);
                selectRight.appendChild(opt.cloneNode(true));
            }
            selectLeft.selectedIndex = names.indexOf(leftName);
            selectRight.selectedIndex = names.indexOf(rightName);

            let leftColor = data[leftName]["color"]
            selectLeft.style.backgroundColor = leftColor
            selectLeft.style.color = contrast(leftColor)

            let rightColor = data[rightName]["color"]
            selectRight.style.backgroundColor = rightColor
            selectRight.style.color = contrast(rightColor)

            function updater(event, right) {
                let garglingData = data[event.target.value]
                let color = garglingData["color"]
                event.target.style.backgroundColor = color
                event.target.style.color = contrast(color)
                let index = right ? 1 : 0
                bothDatasets[index] = garglingData
                update_stats(...bothDatasets)
            }
            selectLeft.addEventListener("change", updater)
            selectRight.addEventListener("change", (event) => updater(event, true))
            return [selectLeft, selectRight]
        })
}

function person_steps(data_as_list, selectLeft, selectRight) {
    let data = to_dict(data_as_list)
    let leftSeries = JSON.parse(JSON.stringify(data[selectLeft.value])); // deep copy
    let rightSeries = JSON.parse(JSON.stringify(data[selectRight.value])); // deep copy
    let bothDatasets = [leftSeries, rightSeries]
    let opts = charts.person_steps
    opts.series = bothDatasets
    let chart = Highcharts.chart('person_steps', opts);
    function updater(event, right) {
        let garglingData = data[event.target.value]
        let index = right ? 1 : 0
        bothDatasets[index] = garglingData
        chart.update({
            series: bothDatasets
        })
    }
    selectLeft.addEventListener("change", updater)
    selectRight.addEventListener("change", (event) => updater(event, true))
}



async function weekday_polar(token, selectLeft, selectRight) {
    const resp = await getBackend(token, "/dashboard/weekday_polar/1");
    const as_list = resp["data"];
    const data = to_dict(as_list)
    let leftSeries = JSON.parse(JSON.stringify(data[selectLeft.value])); // deep copy
    let rightSeries = JSON.parse(JSON.stringify(data[selectRight.value])); // deep copy
    let bothDatasets = [leftSeries, rightSeries];
    let opts = charts.weekday_polar;
    opts.series = bothDatasets;
    let chart = Highcharts.chart('weekday_polar', opts);
    function updater(event, right) {
        let garglingData = data[event.target.value];
        let index = right ? 1 : 0;
        bothDatasets[index] = garglingData;
        chart.update({
            series: bothDatasets
        });
    }
    selectLeft.addEventListener("change", updater);
    selectRight.addEventListener("change", (event_2) => updater(event_2, true));
}


async function month_polar(token, selectLeft, selectRight) {
    const resp = await getBackend(token, "/dashboard/month_polar/1");
    const as_list = resp["data"];
    const data = to_dict(as_list)
    let leftSeries = JSON.parse(JSON.stringify(data[selectLeft.value])); // deep copy
    let rightSeries = JSON.parse(JSON.stringify(data[selectRight.value])); // deep copy
    let bothDatasets = [leftSeries, rightSeries];
    let opts = charts.month_polar;
    opts.series = bothDatasets;
    let chart = Highcharts.chart('month_polar', opts);
    function updater(event, right) {
        let garglingData = data[event.target.value];
        let index = right ? 1 : 0;
        bothDatasets[index] = garglingData;
        chart.update({
            series: bothDatasets
        });
    }
    selectLeft.addEventListener("change", updater);
    selectRight.addEventListener("change", (event_2) => updater(event_2, true));
}


async function countries_timeline(token) {
    const resp = await getBackend(token, "/dashboard/countries_timeline/1");
    const data = resp["data"];
    let opts = charts.countries_timeline;
    opts.series[0].data = data;
    Highcharts.chart('countries_timeline', opts);
}


function distance_area(data) {
    let data_without_avg = data.filter(obj => obj.name !== "Average")
    let opts = charts.distance_area
    opts.series = data_without_avg
    var chart = Highcharts.chart('distance_area', opts);
    let switcher = document.querySelector("#pcswitch")
    switcher.addEventListener("click", function () {
        let mode = switcher.checked ? "percent" : "normal"
        chart.update({
            plotOptions: {
                area: {
                    stacking: mode
                }
            }
        })
    })
}


async function steps_pie(token) {
    const resp = await getBackend(token, "/dashboard/steps_pie/1");
    const data = resp["data"];
    let opts = charts.steps_pie;
    opts.series[0].data = data;
    Highcharts.chart('steps_pie', opts);
}


async function first_place_pie(token) {
    const resp = await getBackend(token, "/dashboard/first_place_pie/1");
    const data = resp["data"];
    let opts = charts.first_place_pie;
    opts.series[0].data = data;
    Highcharts.chart('first_place_pie', opts);
}


async function above_median_pie(token) {
    const resp = await getBackend(token, "/dashboard/above_median_pie/1");
    const data = resp["data"];
    let opts = charts.above_median_pie;
    opts.series[0].data = data;
    Highcharts.chart('above_median_pie', opts);
}


async function contributing_days_pie(token) {
    const resp = await getBackend(token, "/dashboard/contributing_days_pie/1");
    const data = resp["data"];
    let opts = charts.contributing_days_pie;
    opts.series[0].data = data;
    Highcharts.chart('contributing_days_pie', opts);
}


async function main() {
    let slackToken = getToken();
    if (!slackToken) {
        redirectLogin("dashboard")
    }
    let [selectLeft, selectRight] = await personal_stats(slackToken)
    let stepsData = await distance_area_data(slackToken)
    person_steps(stepsData, selectLeft, selectRight)
    weekday_polar(slackToken, selectLeft, selectRight)
    month_polar(slackToken, selectLeft, selectRight)
    countries_timeline(slackToken)
    distance_area(stepsData)
    steps_pie(slackToken)
    first_place_pie(slackToken)
    above_median_pie(slackToken)
    contributing_days_pie(slackToken)
}


main()
