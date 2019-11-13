const webpack = require('webpack');
const dotenv = require('dotenv');
const CopyPlugin = require('copy-webpack-plugin');

const env = dotenv.config().parsed;
const envKeys = Object.keys(env).reduce((prev, next) => {
    prev[`process.env.${next}`] = JSON.stringify(env[next]);
    return prev;
}, {});

module.exports = {
    entry: {
        login: "./src/login.js",
        startTimer: "./src/startTimer.js",
        setBackground: "./src/setBackground.js"
    },
    output: {
        filename: '[name].js',
        path: __dirname + '/dist'
    },
    mode: 'production',
    plugins: [
        new webpack.DefinePlugin(envKeys),
        new CopyPlugin([
            { from: 'src/*.html', flatten: true },
            { from: 'src/*.css', flatten: true }
        ])
    ]
}
