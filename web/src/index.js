import React from "react"
import ReactDOM from "react-dom"
import store from "./store"
import { Provider } from "react-redux"
import {BrowserRouter,Route,Switch} from 'react-router-dom'
import { createHashHistory } from 'history'
import NormalLayout from "./layout/normalLayout"


import  './sass/main.scss'

const app = document.getElementById("react");




ReactDOM.render(
    <Provider store={store}>
        <BrowserRouter >
            <Switch>
                <Route path="/" component={NormalLayout} />
            </Switch>
        </BrowserRouter>
    </Provider>,
    app);