export const backend_url = process.env.backend_url;
export const redirect_url = process.env.redirect_url;
export const ext = process.env.ext;

export const slack_client_id = process.env.slack_client_id;

export const countdown_date = new Date(Date.parse(process.env.countdown_date))
export const countdown_args = process.env.countdown_args;
export const countdown_message = process.env.countdown_message;
export const ongoing_message = process.env.ongoing_message;
export const finished_message = process.env.finished_message;

export const mapbox_token = process.env.mapbox_token;

export const prod = process.env.NODE_ENV !== "development"
