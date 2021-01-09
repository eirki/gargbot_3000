"use strict";

import Highcharts from 'highcharts';

import { getToken, redirectLogin, getBackend } from "./utils.js"


function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1 ')
}


async function distance_area_data(token) {
    let res = getBackend(token, "/dashboard/distance_area/1")
    return await res
}


async function personal_stats(token, steps) {
    const stats = (
        await getBackend(token, "/dashboard/personal_stats/1")
    )
    let allGarglingData = {}
    function populateGarglingData(obj, type) {
        for (var data of Object.values(obj["data"])) {
            let garglingData = allGarglingData[data["name"]] || {}
            garglingData[type] = data
            allGarglingData[data["name"]] = garglingData
        }
    }
    populateGarglingData(steps, "steps")
    populateGarglingData(stats, "stats")

    let leftIndex = steps["data"].length - 1
    let rightIndex = 0

    let leftName = steps["data"][leftIndex]["name"]
    let rightName = steps["data"][rightIndex]["name"]

    let leftSeries = JSON.parse(JSON.stringify(allGarglingData[leftName]["steps"])); // deep copy
    let rightSeries = JSON.parse(JSON.stringify(allGarglingData[rightName]["steps"])); // deep copy
    let both_series = [leftSeries, rightSeries]
    let steps_chart = Highcharts.chart('person_steps', {
        chart: {
            zoomType: 'x'
        },
        title: {
            text: "Personlige stats"
        },
        subtitle: {
            text: document.ontouchstart === undefined ?
                'Click and drag in the plot area to zoom in' : 'Pinch the chart to zoom in'
        },
        xAxis: {
            type: 'datetime'
        },
        yAxis: {
            title: {
                text: 'Skritt'
            }
        },
        legend: {
            enabled: false
        },
        series: both_series

    });

    let leftStatset = allGarglingData[leftName]["stats"]
    let rightStatset = allGarglingData[rightName]["stats"]

    let both_statsets = [leftStatset, rightStatset]
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
            console.log(compSign)
            compElem.innerHTML = ` ${compSign} `

        }
    }
    update_stats(...both_statsets)

    let select_left = document.querySelector("#left_gargling")
    let select_right = document.querySelector("#right_gargling")
    let names = Object.keys(allGarglingData)
    names.sort()
    for (var name of names) {
        var opt = document.createElement('option');
        opt.value = name;
        opt.innerHTML = name;
        select_left.appendChild(opt);
        select_right.appendChild(opt.cloneNode(true));
    }
    select_left.selectedIndex = names.indexOf(leftName);
    select_right.selectedIndex = names.indexOf(rightName);

    function updater(event, right) {
        let index = right ? both_series.length - 1 : 0
        let person_steps = allGarglingData[event.target.value]["steps"]
        both_series[index] = person_steps
        steps_chart.update({
            series: both_series
        })
        let person_stats = allGarglingData[event.target.value]["stats"]
        both_statsets[index] = person_stats
        update_stats(...both_statsets)
    }
    select_left.addEventListener("change", updater)
    select_right.addEventListener("change", (event) => updater(event, true))
}


function distance_area(data) {
    let data_without_avg = data["data"].filter(obj => obj.gargling_id >= 0)
    var chart = Highcharts.chart('distance_area', {
        chart: {
            type: 'area',
            zoomType: 'x'
        },
        title: {
            text: 'Skritt per dag'
        },
        xAxis: {
            type: 'datetime',
            title: {
                enabled: false
            }
        },
        yAxis: {
            title: {
                enabled: false
            },
        },
        subtitle: {
            text: document.ontouchstart === undefined ?
                'Click and drag in the plot area to zoom in' : 'Pinch the chart to zoom in'
        },
        tooltip: {
            split: true
        },
        plotOptions: {
            area: {
                stacking: 'normal',
                lineWidth: 0,
                marker: {
                    enabled: false,
                    lineWidth: 0,
                }
            }
        },
        series: data_without_avg
    });
    let switcher = document.querySelector("#pcswitch")
    switcher.addEventListener("click", function () {
        let mode = (switcher.checked ? "percent" : "normal")
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
    const data = (
        await getBackend(token, "/dashboard/steps_pie/1")
            .then(data => data["data"])
    )
    Highcharts.chart('steps_pie', {
        chart: {
            plotBackgroundColor: null,
            plotBorderWidth: null,
            plotShadow: false,
            type: 'pie'
        },
        title: {
            text: 'Andel skritt gått'
        },
        tooltip: {
            pointFormat: '{series.name}: <b>{point.percentage:.1f}%</b>'
        },
        accessibility: {
            point: {
                valueSuffix: '%'
            }
        },
        plotOptions: {
            pie: {
                allowPointSelect: true,
                cursor: 'pointer',
                dataLabels: {
                    enabled: true,
                    format: '<b>{point.name}</b>: {point.percentage:.1f} %'
                }
            }
        },
        series: [{
            name: 'Skritt',
            colorByPoint: true,
            data: data
        }]
    });
}


async function first_place_pie(token) {
    const data = (
        await getBackend(token, "/dashboard/first_place_pie/1")
            .then(data => data["data"])
    )
    Highcharts.chart('first_place_pie', {
        chart: {
            plotBackgroundColor: null,
            plotBorderWidth: null,
            plotShadow: false,
            type: 'pie'
        },
        title: {
            text: 'Antall førsteplasser'
        },
        plotOptions: {
            pie: {
                allowPointSelect: true,
                cursor: 'pointer',
                dataLabels: {
                    enabled: true,
                    format: '<b>{point.name}</b>: {point.y}'
                }
            }
        },
        series: [{
            name: 'Skritt',
            colorByPoint: true,
            data: data
        }]
    });
}


async function above_median_pie(token) {
    const data = (
        await getBackend(token, "/dashboard/above_median_pie/1")
            .then(data => data["data"])
    )
    Highcharts.chart('above_median_pie', {
        chart: {
            plotBackgroundColor: null,
            plotBorderWidth: null,
            plotShadow: false,
            type: 'pie'
        },
        title: {
            text: 'Andel dager i top 50 %'
        },
        plotOptions: {
            pie: {
                allowPointSelect: true,
                cursor: 'pointer',
                dataLabels: {
                    enabled: true,
                    format: '<b>{point.name}</b>: {point.y}'
                }
            }
        },
        series: [{
            name: 'Skritt',
            colorByPoint: true,
            data: data
        }]
    });
}


async function contributing_days_pie(token) {
    const data = (
        await getBackend(token, "/dashboard/contributing_days_pie/1")
            .then(data => data["data"])
    )
    Highcharts.chart('contributing_days_pie', {
        chart: {
            plotBackgroundColor: null,
            plotBorderWidth: null,
            plotShadow: false,
            type: 'pie'
        },
        title: {
            text: 'Antall dager med contribution på over null'
        },
        plotOptions: {
            pie: {
                allowPointSelect: true,
                cursor: 'pointer',
                dataLabels: {
                    enabled: true,
                    format: '<b>{point.name}</b>: {point.y}'
                }
            }
        },
        series: [{
            name: 'Skritt',
            colorByPoint: true,
            data: data
        }]
    });
}


async function main() {
    let slackToken = getToken();
    if (!slackToken) {
        redirectLogin("dashboard")
    }
    let data = await distance_area_data(slackToken)
    personal_stats(slackToken, data)
    distance_area(data)
    steps_pie(slackToken)
    first_place_pie(slackToken)
    above_median_pie(slackToken)
    contributing_days_pie(slackToken)
}


main()
