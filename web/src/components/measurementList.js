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


    // exportFile(dataCenter, deviceType) {
    //     console.log(http.urlFormat(http.url.MODEL_EXPORT_TIME_SERIES_DATA.url, dataCenter, deviceType));
    //     window.open(http.urlFormat(http.url.MODEL_EXPORT_TIME_SERIES_DATA.url, dataCenter, deviceType));
    // }
    //
    // uploadFile(dataCenter, deviceType, event) {
    //     var data = new FormData();
    //     data.append('file', event.target.files[0]);
    //     axios.post(http.urlFormat(http.url.MODEL_IMPORT_TIME_SERIES_DATA.url, dataCenter, deviceType), data).then(function (item) {
    //         alert("upload success");
    //     })
    // }

    componentWillMount() {
        this.props.dispatch(getMeasurementList());
    }

    render() {
        let self = this;
        let dataCenter = "openlab";
        let openLab = this.props.measurement_list[dataCenter] || {};
        if (openLab && openLab['device_types']) {
            openLab = openLab['device_types'];
        }
        let keys = Object.keys(openLab);
        return (
            <div>
                {
                    Object.keys(this.props.measurement_list).map(function (centerName, cIdx) {
                        let deviceTypes = self.props.measurement_list[centerName]['device_types'];
                        return (
                            <div key={cIdx}>
                                <h2> {centerName}</h2>
                                {
                                    Object.keys(deviceTypes)
                                        .map(function (typeName, tIdx) {
                                            let measurements = deviceTypes[typeName];
                                            return (
                                                <div key={tIdx} className="mb-40">
                                                    <div> <Link to={"/show-data/" + centerName + "/" + typeName}>{typeName}</Link></div>
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
                                                            Object.keys(measurements).map(function (key, idx) {
                                                                return (
                                                                    <tr key={idx}>
                                                                        <td>{idx}</td>
                                                                        <td><Link
                                                                            to={"/show-data/" + centerName + "/" + typeName + "/" + key}> {key}</Link>
                                                                        </td>
                                                                        <td>{
                                                                            Object.keys(measurements[key]['attribute']).map(function (name, i) {
                                                                                return (
                                                                                    <div key={i}>
                                                                                        {name}
                                                                                        : {measurements[key]['attribute'][name]}
                                                                                    </div>
                                                                                )
                                                                            })
                                                                        }
                                                                        </td>
                                                                        <td>
                                                                            {
                                                                                measurements[key]['devices'].map(function (name, i) {
                                                                                    return (
                                                                                        <div key={i}>
                                                                                            <Link
                                                                                                to={"/show-data/" + centerName + "/" + typeName + "/" + key + "/" + name}> {name}</Link>
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
                                            );
                                        })
                                }
                            </div>
                        );
                    })
                }

                {

                }
            </div>
        );
    }
}