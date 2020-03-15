"use strict";

import * as config from "./config.js"

// https://hibbard.eu/how-to-center-an-html-element-using-javascript/
function center_elem(elem) {
    var w = document.documentElement.clientWidth,
        h = document.documentElement.clientHeight;
    elem.style.position = 'absolute';
    elem.style.left = (w - elem.offsetWidth) / 2 + 'px';
    elem.style.top = (h - elem.offsetHeight) / 2 + window.pageYOffset + 'px';
}


function main() {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString)
    const state = urlParams.get("state")
    let url = new URL("https://slack.com/oauth/authorize")
    url.searchParams.set("scope", "identity.basic")
    url.searchParams.set("client_id", config.slack_client_id)
    url.searchParams.set("user_scope", "identify")
    url.searchParams.set("state", state)
    let link = document.createElement("a");
    link.href = url

    let img = document.createElement("img");
    img.src = "https://api.slack.com/img/sign_in_with_slack.png";
    img.alt = "Sign in with Slack";
    img.srcset = "https://platform.slack-edge.com/img/sign_in_with_slack.png 1x, https://platform.slack-edge.com/img/sign_in_with_slack@2x.png 2x"

    link.appendChild(img);
    document.body.appendChild(link);
    img.onload = function () {
        center_elem(this);
    }
}


main()
