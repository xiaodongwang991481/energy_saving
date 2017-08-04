import React from "react"
import {Button, Table, Form, FormGroup, FormControl, Row, Col, ControlLabel} from "react-bootstrap"
import {connect} from "react-redux"
import {
    getMeasurementData,
    getDeviceData,
    cleanDeviceData,
    cleanMeasurementData,
    getDeviceTypeData,
    cleanDeviceTypeData
} from "../actions/modelAction"
import http from "../util/http"
import axios from "axios"


@connect((store) => {
    return {
        measurement_data: store.model.measurement_data,
        device_data: store.model.device_data,
        device_type_data: store.model.device_type_data
    }
})
export default class ShowData extends React.Component {
    constructor(props) {
        super(props)
        this.isDevice = false;
        if (this.props.match.params['device']) {
            this.isDevice = true;
        }
        this.isMeasurement = false;
        if (this.props.match.params['measurement']) {
            this.isMeasurement = true;
        }

        var state = {};
        state.startDate = "2017-07-05";
        state.endDate = "2017-07-06";
        state.aggregation = 300;
        state.aggregation_type = "mean";
        this.state = state;

    }

    componentWillMount() {
        this.props.dispatch(cleanDeviceData());
        this.props.dispatch(cleanMeasurementData());
        this.props.dispatch(cleanDeviceData());
        this.refreshData();
    }

    refreshData() {
        var param = Object.assign({}, this.props.match.params, this.state);
        param['startDate'] += "T00:00:00";
        param['endDate'] += "T23:59:59";
        if (this.isDevice) {
            this.props.dispatch(getDeviceData(param));
        } else if (this.isMeasurement) {
            this.props.dispatch(getMeasurementData(param));
        } else {
            // this.props.dispatch(getDeviceTypeData(param));
        }
    }

    onChange(event) {
        console.log(event);
        var target = event.target;
        var val = target.value;
        var name = target.name;

        this.setState({
            [name]: val
        })
    }

    search() {
        this.refreshData();
        return false;
    }


    exportFile() {
        var url = "";
        var params = this.props.match.params;
        if (this.isMeasurement) {
            url = http.urlFormat(http.url.MODEL_EXPORT_MEASUREMENT_DATA.url, params['data_center'], params['device_type'], params['measurement']);
        } else {
            url = http.urlFormat(http.url.MODEL_EXPORT_DEVICE_TYPE_DATA.url, params['data_center'], params['device_type']);
        }

        url += "?aggregation=" + this.state['aggregation_type'] + "&group_by=time(" + this.state['aggregation'] + "s)&starttime=" + this.state['startDate'] + "&endtime=" + this.state['endDate'];
        console.log(url);
        window.open(url);
    }

    uploadFile(event) {
        console.log(event);
        var data = new FormData();
        data.append('file', event.target.files[0]);
        var params = this.props.match.params;
        if (this.isMeasurement) {
            axios.post(http.urlFormat(http.url.MODEL_IMPORT_DEVICE_TYPE_DATA.url, params['data_center'], params['device_type']), data).then(function (item) {
                alert("upload success");
            })
        } else {
            axios.post(http.urlFormat(http.url.MODEL_IMPORT_MEASUREMENT_DATA.url, params['data_center'], params['device_type'], params['measurement']), data).then(function (item) {
                alert("upload success");
            })
        }

    }

    getDeviceTypeTable(data) {
        return "";
    }

    getDeviceTable(data) {
        let date = Object.keys(data);
        date.sort(function (a, b) {
            return (+new Date(a)) - (new Date(b));
        });


        return (
            <Table striped bordered condensed hover>
                <thead>
                <tr>
                    <th>Date</th>
                    <th>
                        {
                            this.props.match.params['device']
                        }
                    </th>
                </tr>
                </thead>
                <tbody>
                {
                    date.map(function (dateStr, idxR) {
                        return ( <tr key={idxR}>
                            <td>{dateStr}</td>
                            <td>
                                {
                                    data[dateStr]
                                }
                            </td>
                        </tr>);
                    })
                }
                </tbody>
            </Table>);
    }

    getMeasurementTable(data) {
        let deviceNames = Object.keys(data);
        if(deviceNames.length == 0){
            return "";
        }

        var date = Object.keys(data[deviceNames[0]]);
        date.sort(function (a, b) {
            return (+new Date(a)) - (new Date(b));
        });
        return (
            <Table striped bordered condensed hover>
                <thead>
                <tr>
                    <th>Date</th>
                    {
                        deviceNames.map(function (name, idx) {
                            return (
                                <th key={idx}>
                                    {name}
                                </th>
                            );
                        })
                    }
                </tr>
                </thead>
                <tbody>
                {
                    date.map(function (dateStr, idxR) {
                        return ( <tr key={idxR}>
                            <td>{dateStr}</td>
                            {
                                deviceNames.map(function (name, idxC) {
                                    let val = data[name][dateStr] !== undefined ? data[name][dateStr] : "-";
                                    return (
                                        <td key={idxC}>
                                            {val}
                                        </td>
                                    );
                                })
                            }
                        </tr>);
                    })
                }
                </tbody>
            </Table>
        );
    }

    render() {
        let table = "";
        if (this.isDevice) {
            table = this.getDeviceTable(this.props.device_data.data);
        } else if (this.isMeasurement) {
            table = this.getMeasurementTable(this.props.measurement_data.data);
        }else{
            table = this.getDeviceTypeTable(this.props.device_type_data.data);
        }
        var action = [];
        if(this.isDevice || this.isMeasurement){
            action.push(
                <Button className="mb-10 mr-20" onClick={this.search.bind(this)}>
                    Search
                </Button>
            );
        }

        if (!this.isDevice) {
            action.push(<label className="btn mb-10 mr-20 btn-primary">
                Import <input type="file" className="hidden"
                              onChange={this.uploadFile.bind(this)}/>
            </label>);

            action.push(<Button className="mb-10 mr-20" bsStyle="success" onClick={this.exportFile.bind(this)}>
                Export
            </Button>);
        }

        return (

            <div className="mb-20 ml-20 mr-20">
                <Row>
                    <Form  >
                        <Col xs={3}>
                            <FormGroup controlId="start-date">
                                <ControlLabel>Type</ControlLabel>
                                {/*<FormControl name="aggregation" placeholder="aggregation" type="number"*/}
                                {/*value={this.state.aggregation} onChange={this.onChange.bind(this)}*/}
                                {/*size="10"/>*/}
                                <FormControl componentClass="select" name="aggregation_type"
                                             onChange={this.onChange.bind(this)}
                                             value={this.state.aggregation_type}>
                                    <option value="mean">mean</option>
                                </FormControl>
                            </FormGroup>
                        </Col>
                        <Col xs={3}>
                            <FormGroup controlId="start-date">
                                <ControlLabel>Aggregation</ControlLabel>
                                <FormControl name="aggregation" placeholder="aggregation" type="number"
                                             value={this.state.aggregation} onChange={this.onChange.bind(this)}
                                             size="10"/>
                            </FormGroup>
                        </Col>
                        <Col xs={3}>
                            <FormGroup controlId="start-date">
                                <ControlLabel>Start Time</ControlLabel>
                                <FormControl name="startDate" placeholder="start date" type="date"
                                             value={this.state.startDate} onChange={this.onChange.bind(this)}
                                             size="10"/>
                            </FormGroup>
                        </Col>
                        <Col xs={3}>
                            <FormGroup controlId="end-date">
                                <ControlLabel>End Time</ControlLabel>
                                <FormControl name="endDate" placeholder="end date" type="date"
                                             value={this.state.endDate} onChange={this.onChange.bind(this)} size="10"/>
                            </FormGroup>
                        </Col>

                        <Col xs={12}>
                            {action}
                        </Col>

                    </Form>
                </Row>
                <div style={{'overflowX': 'auto'}}>
                    {table}
                </div>


            </div>
        )
    }
}

