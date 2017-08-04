/**
 * Created by su on 6/14/17.
 */


import axios from "axios"
import store from "../store"
import {changeLoadingState} from "../actions/utilAction"

class Http {
    constructor(){
        this.initUrl();
        this.initInterceptors();
        this.requestCount = 0;
    }

    initUrl(){
        var prefix = "/api/";
        this.url = {
            GET_TIME_SERIES_DATE:{
                url: prefix + 'timeseries'
            },
            MODEL_GET_MODEL_LIST:{
                url : prefix + 'metadata/database/models'
            },
            MODEL_IMPORT : {
                url : prefix + 'import/database/{0}'
            },
            MODEL_GET_MEASUREMENT_LIST:{
                url : prefix + 'metadata/timeseries/models'
            },
            MODEL_GET_DEVICE_TYPE_DATA:{
                url : prefix + "timeseries/{0}/{1}"
            },
            MODEL_GET_MEASUREMENT_DATA:{
                url : prefix + 'timeseries/{0}/{1}/{2}'
            },
            MODEL_GET_DEVICE_DATA:{
                url : prefix + 'timeseries/{0}/{1}/{2}/{3}'
            },
            MODEL_IMPORT_DEVICE_TYPE_DATA:{
                url : prefix + 'import/timeseries/{0}/{1}'
            },
            MODEL_EXPORT_DEVICE_TYPE_DATA:{
                url : prefix + 'export/timeseries/{0}/{1}'
            },
            MODEL_IMPORT_MEASUREMENT_DATA:{
                url : prefix + 'import/timeseries/{0}/{1}/{2}'
            },
            MODEL_EXPORT_MEASUREMENT_DATA:{
                url : prefix + 'export/timeseries/{0}/{1}/{2}'
            },
            MODEL_GET_ALL_MODEL_TYPES : {
                url : prefix + "models/{0}"
            },
            MODEL_BUILD_MODEL : {
                url : prefix + "models/{0}/{1}/build"
            },
            MODEL_TRAIN_MODEL : {
                url : prefix + "models/{0}/{1}/train"
            },
            MODEL_TEST_MODEL : {
                url : prefix + "models/{0}/{1}/test"
            },
            MODEL_APPLY_MODEL : {
                url : prefix + "models/{0}/{1}/apply"
            }
        }
    }


    urlFormat(str){
        var args = Array.prototype.slice.call(arguments,1);
        return str.replace(/{(\d+)}/g,function(match, number){
            return typeof args[number] != undefined
                ? args[number] : match;
        });
    }

    initInterceptors() {
        let self = this;
        axios.interceptors.request.use(function (config) {
            self.requestCount ++;
            if(store.getState()['util']['loading'] == false){
                store.dispatch(changeLoadingState(true));
            }
            return config;
        }, function (error) {
            return Promise.reject(error);
        });

        axios.interceptors.response.use(function (response) {
            self.requestCount --;
            if(self.requestCount == 0 && store.getState()['util']['loading'] ){
                store.dispatch(changeLoadingState(false));
            }
            return response;
        }, function (error) {
            window.alert(JSON.stringify(error,"",2));
            self.requestCount --;
            if(self.requestCount == 0 && store.getState()['util']['loading'] ){
                store.dispatch(changeLoadingState(false));
            }
            return Promise.reject(error);
        });
    }




}

const http = new Http();
export default http;
