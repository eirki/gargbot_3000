"use strict";

import 'leaflet/dist/leaflet.css';
import '@raruto/leaflet-elevation/dist/leaflet-elevation.css';
import L from 'leaflet'
import * as elevation from '@raruto/leaflet-elevation';

import { getToken, redirectLogin, getBackend } from "./utils.js"
import * as config from "./config.js"

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
    iconUrl: require('leaflet/dist/images/marker-icon.png'),
    shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

const journey_id = 2;

// https://leaflet-extras.github.io/leaflet-providers/preview/
const tileServer = (
    config.prod ?
        'https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}' :
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
)
const attr = 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>';


function journeyDetails(token) {
    return getBackend(token, `/detail_journey/${journey_id}`)
}

function defineMap() {
    var map = L.map('mapid')
    L.tileLayer(tileServer, {
        attribution: attr,
        maxZoom: 15,
        id: 'mapbox/streets-v11',
        tileSize: 512,
        zoomOffset: -1,
        accessToken: config.mapbox_token
    }).addTo(map);
    return map
}


function addLine(map, data) {
    var elevation_options = {
        theme: "lightblue-theme",
        detached: true,
        elevationDiv: "#elevation",
        followMarker: true,
        slope: false,
        speed: false,
        time: false,
        summary: false,
        ruler: false,
        legend: false,
    };
    let waypoints = data["waypoints"]
    let line = L.geoJSON(waypoints)
    map.fitBounds(line.getBounds());
    var controlElevation = L.control.elevation(elevation_options).addTo(map);
    let geojson = {
        "name": "demo.geojson",
        "type": "FeatureCollection",
        "features": [{
            "properties": null,
            "type": "Feature",
            "geometry": waypoints
        }]
    }
    controlElevation.load(geojson);
}


function addMarkers(map, data) {
    var smallMarkers = new L.FeatureGroup();
    var bigMarkers = new L.FeatureGroup();
    function zoomHandler() {
        var currentZoom = map.getZoom();
        if (currentZoom < 6) {
            map.removeLayer(bigMarkers);
            map.addLayer(smallMarkers);
        }
        else {
            map.removeLayer(smallMarkers);
            map.addLayer(bigMarkers);
        }
    }
    zoomHandler()
    let last_distance = 0;

    for (const [i, location] of data["locations"].entries()) {
        let bigMarker = L.marker(location)
        let smallMarker = L.circleMarker(location, { radius: 1 })
        bigMarkers.addLayer(bigMarker);
        smallMarkers.addLayer(smallMarker);

        let popupElem = document.createElement('div')

        bigMarker.bindPopup(popupElem);
        smallMarker.bindPopup(popupElem)

        let date_obj = new Date(location["date"])

        const date_options = { weekday: 'short', year: 'numeric', month: 'long', day: 'numeric' };
        let date_str = date_obj.toLocaleDateString("no-NB", date_options)
        date_str = date_str[0].toUpperCase() + date_str.slice(1)
        let p
        p = document.createElement('p')
        p.innerHTML = `<b>Dag ${i + 1}</b>`
        popupElem.appendChild(p)
        p = document.createElement('p')
        p.innerHTML = date_str
        popupElem.appendChild(p)

        p = document.createElement('p')
        let days_distance = location["distance"] - last_distance
        p.innerHTML = `
            Dagens distanse: ${Math.round(days_distance / 1000)} km<br>
            Sammenlagt distanse: ${Math.round(location["distance"] / 1000)} km
        `
        popupElem.appendChild(p)
        last_distance = location["distance"]

        if (location["address"] != null) {
            p = document.createElement('p')
            p.innerHTML = location["address"]
            popupElem.appendChild(p)
        }
        if (location["poi"] != null) {
            p = document.createElement('p')
            p.innerHTML = `Dagens underholdning: ${location["poi"]}`
            popupElem.appendChild(p)
        }
        if (location["photo_url"] != null) {
            let img = document.createElement('img');
            img.classList.add("location_img")
            img.src = location["photo_url"]
            popupElem.appendChild(img)
        }
    }
    map.on('zoomend', zoomHandler);
}

async function main() {
    let slackToken = getToken();
    if (!slackToken) {
        // not logged in to slack
        redirectLogin("dashboard")
    }
    let data = await journeyDetails(slackToken)
    let map = defineMap()
    addLine(map, data)
    addMarkers(map, data)
}


main()
