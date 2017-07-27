const webpack = require("webpack");
const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const CleanWebpackPlugin = require('clean-webpack-plugin')

const APP_DIR = path.resolve(__dirname, './src');
const BUILD_DIR = path.resolve(__dirname, './build');

var config = {
    context: APP_DIR,
    entry: {
        javascript: APP_DIR + '/index.js'
    },
    module: {
        rules: [{
            test: /\.html$/i,
            use: 'html-loader'
        }, {
            test: /\.jsx?$/,
            include: [
                path.resolve(__dirname, 'src')
            ],
            exclude: /node_modules/,
            loader: "babel-loader",
            query: {
                presets: ['es2015', 'react', 'stage-2'],
                plugins: ['transform-runtime', 'transform-decorators-legacy']
            }
        }, {
            test: /\.css$/,
            use: ['style-loader', 'css-loader'],
        }, {
            test: /\.png$/,
            use: [{
                loader: "url-loader",
                options: {
                    limit: 100000
                }
            }],
        }, {
            test: /\.(jpeg|jpg)$/,
            use: [{
                loader: "file-loader"
            }]
        }, {
            test: /\.(woff|woff2)(\?v=\d+\.\d+\.\d+)?$/,
            use: [{
                loader: "url-loader",
                options: {
                    limit: 10000,
                    mimetype: "application/font-woff"
                }
            }]
        }, {
            test: /\.ttf(\?v=\d+\.\d+\.\d+)?$/,
            use: [{
                loader: "url-loader",
                options: {
                    limit: 10000,
                    mimetype: "application/octet-stream"
                }
            }]
        }, {
            test: /\.eot(\?v=\d+\.\d+\.\d+)?$/,
            use: [{
                loader: 'file-loader'
            }]
        }, {
            test: /\.svg(\?v=\d+\.\d+\.\d+)?$/,
            use: [{
                loader: "url-loader",
                options: {
                    limit: 10000,
                    mimetype: "image/scg+xml"
                }
            }]
        },{
            test: /\.less$/,
            use:['style-loader', 'css-loader', 'less-loader' ]
        },{
            test: /\.scss$/,
            use: [{
                loader: "style-loader" // creates style nodes from JS strings
            }, {
                loader: "css-loader" // translates CSS into CommonJS
            }, {
                loader: "sass-loader" // compiles Sass to CSS
            }]
        }]
    },
    output: {
        publicPath : '/',
        path: BUILD_DIR,
        filename: 'bundle.js'
    },
    plugins: [
        new CleanWebpackPlugin(BUILD_DIR),
        new HtmlWebpackPlugin({template: './index.html'}),
        new webpack.DefinePlugin({
            'process.env': {
                'API_HOST': JSON.stringify(process.env.API_HOST )
            }
        })
    ],
    devServer: {
        port: 9999,
        proxy: {
            "/api": "http://10.145.89.250:8080"
        },
        historyApiFallback: true,

    }
}


module.exports = config;