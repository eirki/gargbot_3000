"use strict";

import Highcharts from 'highcharts';

import { getToken, redirectLogin } from "./common.js"
import * as config from "./config.js"


function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1 ')
}


async function distance_area_data(token) {
    const url = new URL(`/dashboard/distance_area/1`, config.backend_url)
    console.log(`Fetching ${url}`)
    return await fetch(url, {
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
        });
}


async function personal_stats(token, steps) {
    const url = new URL(`/dashboard/personal_stats/1`, config.backend_url)
    console.log(`Fetching ${url}`)
    const stats = await fetch(url, {
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
        });
    steps["data"].reverse()
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
        series: [JSON.parse(JSON.stringify(steps["data"][0]))], // deep copy

    });
    function update_stats(obj) {
        let parent = document.getElementById("person_stats")
        let chldrn = parent.getElementsByTagName("p")
        for (let chld of chldrn) {
            chld.innerHTML = formatNumber(obj[chld.id])
        }
    }
    update_stats(stats["data"][0])

    let allGarglingData = {}
    function populateGarglingData(obj, name) {
        for (var data of Object.values(obj["data"])) {
            let garglingData = allGarglingData[data["name"]] || {}
            garglingData[name] = data
            allGarglingData[data["name"]] = garglingData
        }
    }
    populateGarglingData(steps, "steps")
    populateGarglingData(stats, "stats")
    let select = document.getElementById("select_gargling")
    for (var [name, data] of Object.entries(allGarglingData)) {
        var opt = document.createElement('option');
        opt.value = name;
        opt.innerHTML = data["steps"]["name"];
        select.appendChild(opt);
    }

    select.addEventListener("change", (event) => {
        let person_steps = allGarglingData[event.target.value]["steps"]
        steps_chart.update({
            series: [person_steps]
        })
        let person_stats = allGarglingData[event.target.value]["stats"]
        update_stats(person_stats)
    })
}


function distance_area(data) {
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
                lineColor: '#FFFFFF',
                lineWidth: 1,
                marker: {
                    enabled: false,
                    lineWidth: 1,
                    lineColor: '#FFFFFF'
                }
            }
        },
        series: data["data"]
    });
    let switcher = document.getElementById("pcswitch")
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
    const url = new URL(`/dashboard/steps_pie/1`, config.backend_url)
    console.log(`Fetching ${url}`)
    const data = await fetch(url, {
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
            let dd = data["data"]
            return dd
        })
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
    const url = new URL(`/dashboard/first_place_pie/1`, config.backend_url)
    console.log(`Fetching ${url}`)
    const data = await fetch(url, {
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
            let dd = data["data"]
            return dd
        })
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
    const url = new URL(`/dashboard/above_median_pie/1`, config.backend_url)
    console.log(`Fetching ${url}`)
    const data = await fetch(url, {
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
            let dd = data["data"]
            return dd
        })
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
    const url = new URL(`/dashboard/contributing_days_pie/1`, config.backend_url)
    console.log(`Fetching ${url}`)
    const data = await fetch(url, {
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
            let dd = data["data"]
            return dd
        })
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
        // not logged in to slack
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
