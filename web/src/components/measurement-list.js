import React from "react"
import {connect} from "react-redux"
import {getMeasurementList} from "../actions/modelAction"
import {Table, Button} from "react-bootstrap"
import {Link} from "react-router-dom"
import axios from "axios"
import http from "../util/http"

@connect((store) => {
    return {
        measurement_list: store.model.measurement_list
    }
})
export default class MeasurementList extends React.Component {
    constructor(props) {
        super(props);
    }


    exportFile(dataCenter, deviceType) {
        console.log(http.urlFormat(http.url.MODEL_EXPORT_TIME_SERIES_DATA.url,dataCenter,deviceType));
        window.open(http.urlFormat(http.url.MODEL_EXPORT_TIME_SERIES_DATA.url,dataCenter,deviceType));
    }

    uploadFile(dataCenter, deviceType, event) {
        var data = new FormData();
        data.append('file', event.target.files[0]);
        axios.post(http.urlFormat(http.url.MODEL_IMPORT_TIME_SERIES_DATA.url,dataCenter,deviceType) ,data).then(function(item){
            alert("upload success");
        })
    }

    componentWillMount() {
        this.props.dispatch(getMeasurementList());
    }

    render() {
        let self = this;
        let dataCenter = "openlab";
        let openLab = this.props.measurement_list[dataCenter] || {};
        let keys = Object.keys(openLab['device_types']);
        return (
            <div>
                {
                    keys.map(function (item, index) {
                        return (
                            <div key={index} className="mb-40">
                                <div>{item}</div>
                                <Button className="mt-10 mb-10 mr-10" bsStyle="success"
                                        onClick={self.exportFile.bind(self, dataCenter, item)}>export</Button>
                                <label className="btn btn-primary mt-10 mb-10">
                                    Import <input type="file" className="hidden"
                                                  onChange={self.uploadFile.bind(this, dataCenter, item)}/>
                                </label>
                                <Table striped bordered condensed hover>
                                    <thead>
                                    <tr>
                                        <th>#</th>
                                        <th>Name</th>
                                        <th>Atribute</th>
                                        <th>Devices</th>
                                    </tr>
                                    </thead>
                                    <tbody>
                                    {
                                        Object.keys(openLab['device_types'][item]).map(function (key, idx) {
                                            return (
                                                <tr key={idx}>
                                                    <td>{idx}</td>
                                                    <td><Link
                                                        to={"/show-data/openlab/" + item + "/" + key}> {key}</Link>
                                                    </td>
                                                    <td>{
                                                        Object.keys(openLab['device_type'][item][key]['attribute']).map(function (name, i) {
                                                            return (
                                                                <div key={i}>
                                                                    {name} : {openLab['device_type'][item][key]['attribute'][name]}
                                                                </div>
                                                            )
                                                        })
                                                    }
                                                    </td>
                                                    <td>
                                                        {
                                                            openLab['device_types'][item][key]['devices'].map(function (name, i) {
                                                                return (
                                                                    <div key={i}>
                                                                        <Link
                                                                            to={"/show-data/openlab/" + item + "/" + key + "/" + name}> {name}</Link>
                                                                    </div>
                                                                )
                                                            })
                                                        }
                                                    </td>
                                                </tr>
                                            )
                                        })
                                    }
                                    </tbody>
                                </Table>
                            </div>
                        )
                    })
                }
            </div>
        );
    }
}
