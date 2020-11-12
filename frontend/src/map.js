"use strict";

import 'leaflet/dist/leaflet.css';
import L from 'leaflet'
delete L.Icon.Default.prototype._getIconUrl;

import { getToken, redirectLogin } from "./common.js"
import * as config from "./config.js"

L.Icon.Default.mergeOptions({
    iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
    iconUrl: require('leaflet/dist/images/marker-icon.png'),
    shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

const attr = 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>';

const tileServer = 'https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}'
// https://leaflet-extras.github.io/leaflet-providers/preview/
// const tileServer = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"

function journeyDetails(token) {
    const url = new URL("/detail_journey/1", config.backend_url)
    console.log(`Fetching ${url}`)
    return fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': 'Bearer ' + token
        }
    })
        .then(response => response.json());

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
    let latlngs = data["waypoints"]
    var polyline = L.polyline(latlngs, { color: 'teal' }).addTo(map);
    map.fitBounds(polyline.getBounds());
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
        let popupContent = `
            Dag ${i + 1}<br>
            ${date_str}
        `
        if (location["address"] != null) {
            popupContent = popupContent.concat(`<br>${location["address"]}`)
        }
        if (location["poi"] != null) {
            popupContent = popupContent.concat(`<br><br>Kveldens underholdning: ${location["poi"]}`)
        }
        popupElem.innerHTML = popupContent
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
