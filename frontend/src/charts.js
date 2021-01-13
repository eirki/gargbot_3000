export let person_steps = {
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
    tooltip: {
        split: true
    },
    legend: {
        enabled: false
    },
}

export let weekday_polar = {
    chart: {
        type: 'column',
        polar: true
    },
    title: {
        text: 'Avg. skritt per ukedag'
    },
    xAxis: {
        categories: [
            'Mon',
            'Tue',
            'Wed',
            'Thu',
            'Fri',
            'Sat',
            'Sun',
        ],
        gridLineColor: '#4c4c4c'
    },
    yAxis: {
        gridLineColor: '#4c4c4c'
    },
    plotOptions: {
        column: {
            pointPadding: 0,
            groupPadding: 0
        }
    },
    legend: {
        enabled: false
    }
}

export let month_polar = {
    chart: {
        type: 'column',
        polar: true
    },
    title: {
        text: 'Average daglig skritt per måned'
    },
    xAxis: {
        categories: [
            'Jan',
            'Feb',
            'Mar',
            'Apr',
            'May',
            'Jun',
            'Jul',
            'Aug',
            'Sep',
            'Oct',
            'Nov',
            'Dec'
        ],
        gridLineColor: '#4c4c4c'
    },
    yAxis: {
        gridLineColor: '#4c4c4c'
    },
    plotOptions: {
        column: {
            pointPadding: 0,
            groupPadding: 0
        }
    },
    tooltip: {
        split: true
    },
    legend: {
        enabled: false
    }
}

export let countries_timeline = {
    chart: {
        zoomType: 'x',
        type: 'timeline'
    },
    xAxis: {
        type: 'datetime',
        visible: false
    },
    yAxis: {
        gridLineWidth: 1,
        title: null,
        labels: {
            enabled: false
        }
    },
    legend: {
        enabled: false
    },
    title: {
        text: 'Timeline of countries'
    },
    tooltip: {
        enabled: false,
    },
    series: [{
        dataLabels: {
            format: '<span style="color:{point.color}">● </span><span style="font-weight: bold;" > ' +
                '{point.x:%d %b %Y}</span><br/>{point.label}'
        },
        marker: {
            symbol: 'circle'
        },
    }]
}

export let distance_area = {
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
}

let pieChartOptions = {
    plotBackgroundColor: null,
    plotBorderWidth: null,
    plotShadow: false,
    type: 'pie'
}

export let steps_pie = {
    chart: pieChartOptions,
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
    }]
}

let piePlotOptions = {
    pie: {
        allowPointSelect: true,
        cursor: 'pointer',
        dataLabels: {
            enabled: true,
            format: '<b>{point.name}</b>: {point.y}'
        }
    }
}

export let first_place_pie = {
    chart: pieChartOptions,
    title: {
        text: 'Antall førsteplasser'
    },
    plotOptions: piePlotOptions,
    series: [{
        name: 'Skritt',
        colorByPoint: true,
    }]
}

export let above_median_pie = {
    chart: pieChartOptions,
    title: {
        text: 'Andel dager i top 50 %'
    },
    plotOptions: piePlotOptions,
    series: [{
        name: 'Skritt',
        colorByPoint: true,
    }]
}

export let contributing_days_pie = {
    chart: pieChartOptions,
    title: {
        text: 'Antall dager med contribution på over null'
    },
    plotOptions: piePlotOptions,
    series: [{
        name: 'Skritt',
        colorByPoint: true,
    }]
}
