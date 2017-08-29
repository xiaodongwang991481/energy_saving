import axios from "axios"
import http from "../util/http"

export function getTaskList(dataCenter){
    return (dispatch)=>{
        axios.get(http.urlFormat(http.url.TASK_GET_TASK_LIST.url,dataCenter)).then(function(res){
            dispatch({
                type:"TASK_GET_TASK_LIST",
                payload:res.data
            })
        })
    }
}

export function getTaskResult(dataCenter,resultId){
    return (dispatch)=>{
        axios.get(http.urlFormat(http.url.TASK_GET_TASK_RESULT.url,dataCenter,resultId)).then(function(res){
            dispatch({
                type:"TASK_GET_TASK_RESULT",
                payload:res.data
            });
        })
    }
}

export function getTaskResultPrediction(dataCenter,resultId,){
    return (dispatch)=>{
        axios.get(http.urlFormat(http.url.TASK_GET_TASK_RESULT_ATTR.url,dataCenter,resultId,"prediction")).then(function(res){
           dispatch({
               type:"TASK_GET_TASK_RESULT_PREDICTION",
               payload:res.data
           })
        });
    }
}

export function getTaskResultExpectation(dataCenter,resultId){
    return (dispatch)=>{
        axios.get(http.urlFormat(http.url.TASK_GET_TASK_RESULT_ATTR.url,dataCenter,resultId,"expectation")).then(function(res){
            dispatch({
                type:"TASK_GET_TASK_RESULT_EXPECTATION",
                payload : res.data
            })
        })
    }
}

export function clearTaskDetail(){
    return {
        type:"TASK_CLEAR_TASK_RESULT"
    }
}


export function getTaskDetailByDevice(dataCenter,resultId,measurementKey,deviceType,measurement,deviceId){
    return (dispatch)=>{
        axios.get(http.urlFormat(http.url.TASK_GET_TASK_RESULT_BY_DEVICE_ATTR.url,dataCenter,resultId,measurementKey,deviceType,measurement,deviceId)).then(function(res){
            if(measurementKey == 'expectation'){
                dispatch({
                    type:"TASK_GET_TASK_RESULT_EXPECTATION",
                    payload:res.data
                })
            }else{
                dispatch({
                    type:"TASK_GET_TASK_RESULT_PREDICTION",
                    payload: res.data
                })
            }
        });
    }
}

export function getTaskResultModeList(dataCenter,resultId){
    return (dispatch)=>{
        axios.get(http.urlFormat(http.url.TASK_GET_TASK_RESULT_MODEL_LIST.url,dataCenter,resultId)).then(function(res){
            dispatch({
                type : "TASK_GET_TASK_RESULT_MODEL_LIST",
                payload : res.data
            })
        })
    }
}

