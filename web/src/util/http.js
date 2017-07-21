/**
 * Created by su on 6/14/17.
 */

class Http {
    constructor(){
        this.initUrl();
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
            MODEL_GET_MEASUREMENT_DATA:{
                url : prefix + 'timeseries/{0}/{1}/{2}'
            },
            MODEL_GET_DEVICE_DATA:{
                url : prefix + 'timeseries/{0}/{1}/{2}/{3}'
            },
            MODEL_IMPORT_TIME_SERIES_DATA:{
                url : prefix + 'import/timeseries/{0}/{1}'
            },
            MODEL_EXPORT_TIME_SERIES_DATA :{
                url : prefix + 'export/timeseries/{0}/{1}'
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
}

const http = new Http();
export default http;
