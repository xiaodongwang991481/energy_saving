import axios from "axios"
import http from "../util/http"

export function getModelList(){
    return (dispatch)=>{
        axios.get(http.url.MODEL_GET_MODEL_LIST.url).then(function(res){
           dispatch({
               type:"MODEL_GET_MODEL_LIST",
               payload : res.data
           })
        });
    }
}


export function getMeasurementList(){
    return (dispatch)=>{
        axios.get(http.url.MODEL_GET_MEASUREMENT_LIST.url).then(function (res) {
            dispatch({
                type:"MODEL_GET_MEASUREMENT_LIST",
                payload : res.data
            })
        })
    }
}


export function getMeasurementData(param){
    return (dispatch)=>{
        axios.get(http.urlFormat(http.url.MODEL_GET_MEASUREMENT_DATA.url,
            param['data_center'],param['device_type'],param['measurement'])).then(function(res){
            dispatch({
                type:"MODEL_GET_MEASUREMENT_DATA",
                payload : res.data
            })
        })
    }
}

export function getDeviceData(param){
    return (dispatch)=>{
        axios.get(http.urlFormat(http.url.MODEL_GET_DEEVICE_DATA.url,
            param['data_center'],param['device_type'],param['measurement'],param['device'])).then(function(res){
            dispatch({
                type:"MODEL_DEVICE_DATA",
                payload : res.data
            })
        })
    }
}