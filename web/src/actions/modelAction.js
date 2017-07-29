import axios from "axios"
import http from "../util/http"

export function getModelList(data) {
    return {
        type: "MODEL_GET_MODEL_LIST",
        payload: data
    };
}


export function getMeasurementList() {
    return (dispatch) => {
        axios.get(http.url.MODEL_GET_MEASUREMENT_LIST.url).then(function (res) {
            dispatch({
                type: "MODEL_GET_MEASUREMENT_LIST",
                payload: res.data
            })
        })
    }
}


export function getMeasurementData(param) {
    return (dispatch) => {
        axios.get(http.urlFormat(http.url.MODEL_GET_MEASUREMENT_DATA.url,
                param['data_center'], param['device_type'], param['measurement']) + "?&aggregation=mean&group_by=time(" + param['aggregation'] + "s)&starttime=" + param['startDate'] + "&endtime=" + param['endDate']
        ).then(function (res) {
            dispatch({
                type: "MODEL_GET_MEASUREMENT_DATA",
                payload: {
                    data: res.data,
                }
            })
        })
    }
}

export function getDeviceData(param) {
    return (dispatch) => {
        axios.get(http.urlFormat(http.url.MODEL_GET_DEVICE_DATA.url,
                param['data_center'], param['device_type'], param['measurement'], param['device']) + "?&aggregation=mean&group_by=time(" + param['aggregation'] + "s)&starttime=" + param['startDate'] + "&endtime=" + param['endDate']
        ).then(function (res) {
            dispatch({
                type: "MODEL_DEVICE_DATA",
                payload: {
                    data: res.data,
                }
            })
        })
    }
}

export function cleanDeviceData() {
    return {
        type: "MODEL_DEVICE_DATA",
        payload: {
            data: [],
        }
    };
}

export function cleanMeasurementData() {
    return {
        type: "MODEL_GET_MEASUREMENT_DATA",
        payload: {
            data: [],
        }
    };
}