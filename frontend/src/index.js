"use strict";

import { getToken, redirectLogin } from "./utils.js"


function main() {
    let slackToken = getToken();
    if (!slackToken) {
        redirectLogin("index")
    }
}


main()
