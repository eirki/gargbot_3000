"use strict";

// https://hibbard.eu/how-to-center-an-html-element-using-javascript/
function center_elem(elem) {
    var w = document.documentElement.clientWidth,
        h = document.documentElement.clientHeight;
    elem.style.position = 'absolute';
    elem.style.left = (w - elem.offsetWidth) / 2 + 'px';
    elem.style.top = (h - elem.offsetHeight) / 2 + window.pageYOffset + 'px';
}


function main() {
    var link = document.createElement("a");
    link.href = `https://slack.com/oauth/authorize?scope=identity.basic&client_id=${process.env.client_id}`

    var img = document.createElement("img");
    img.src = "https://api.slack.com/img/sign_in_with_slack.png";
    img.alt = "Sign in with Slack";
    img.srcset = "https://platform.slack-edge.com/img/sign_in_with_slack.png 1x, https://platform.slack-edge.com/img/sign_in_with_slack@2x.png 2x"

    link.appendChild(img);
    document.body.appendChild(link);
    img.onload = function () {
        center_elem(this);
    }

}

main();
