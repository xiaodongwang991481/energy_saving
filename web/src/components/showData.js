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
import HighCharts from "./element/highCharts"


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
        state.viewType = 'table';
        this.state = state;
        this.postForm = null;

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

    changeView(){
        if(this.state.viewType == 'table'){
            this.setState({viewType:'chart'});
        }else{
            this.setState({viewType:'table'});
        }
    }


    exportFile() {
        if (this.postForm) {
            this.postForm.submit();
        }
        // var url = "";
        // var params = this.props.match.params;
        // if (this.isMeasurement) {
        //     url = http.urlFormat(http.url.MODEL_EXPORT_MEASUREMENT_DATA.url, params['data_center'], params['device_type'], params['measurement']);
        // } else {
        //     url = http.urlFormat(http.url.MODEL_EXPORT_DEVICE_TYPE_DATA.url, params['data_center'], params['device_type']);
        // }
        //
        // url += "?aggregation=" + this.state['aggregation_type'] + "&group_by=time(" + this.state['aggregation'] + "s)&starttime=" + this.state['startDate'] + "&endtime=" + this.state['endDate'];
        // console.log(url);
        // window.open(url);
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

        if (this.state.viewType == 'table') {
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
        } else {

            var formattedData = [];
            date.forEach(function (item) {
                formattedData.push([+(new Date(item)), data[item]]);
            })
            var series = [{name: this.props.match.params['device'], data: formattedData}];

            return (
                <HighCharts series={series} title={this.props.match.params['device']}/>
            );
        }

    }

    getMeasurementTable(data) {
        let deviceNames = Object.keys(data);
        if (deviceNames.length == 0) {
            return "";
        }

        var date = Object.keys(data[deviceNames[0]]);
        date.sort(function (a, b) {
            return (+new Date(a)) - (new Date(b));
        });
        if (this.state.viewType == 'table') {
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
        } else {
            var series = [];
            var seriesMap = {};
            deviceNames.forEach(function (name) {
                seriesMap[name] = []
            });
            date.forEach(function (dateStr) {
                deviceNames.forEach(function (name) {
                    let val = data[name][dateStr];
                    seriesMap[name].push([+(new Date(dateStr)), val]);
                })
            });
            deviceNames.forEach(function (name) {
                series.push({name: name, data: seriesMap[name]});
            });

            return (
                <HighCharts series={series} title={this.props.match.params['measurement']}/>
            );
        }

    }

    render() {
        let table = "";
        if (this.isDevice) {
            table = this.getDeviceTable(this.props.device_data.data);
        } else if (this.isMeasurement) {
            table = this.getMeasurementTable(this.props.measurement_data.data);
        } else {
            table = this.getDeviceTypeTable(this.props.device_type_data.data);
        }
        var action = [];


        if (this.isDevice || this.isMeasurement) {

            action.push(
                <Button className="mb-10 mr-20" onClick={this.search.bind(this)}>
                    Search
                </Button>
            );

            action.push(
                <Button className="mb-10 mr-20" onClick={this.changeView.bind(this)}>
                    {this.state.viewType == 'table' ? "Chart" : "Table"}
                </Button>
            );
        }

        if (!this.isDevice) {
            action.push(<label className="btn mb-10 mr-20 btn-primary">
                Import <input type="file" className="hidden"
                              onChange={this.uploadFile.bind(this)}/>
            </label>);


            var url = "/api/export/timeseries/" + this.props.match.params['data_center'];
            if (this.props.match.params['device_type']) {
                url += "/" + this.props.match.params['device_type'];
                if (this.props.match.params['measurement']) {
                    url += "/" + this.props.match.params['measurement'];
                }
            }
            action.push(
                <Button className="mb-10 mr-20" bsStyle="success" onClick={this.exportFile.bind(this)}>
                    Export
                </Button>
            );
            action.push(
                <form method="post" className="hidden" ref={(form) => {
                    this.postForm = form;
                }} action={url} enctype="multipart/form-data">
                    <input className="hidden" name="aggregation" value={this.state.aggregation_type}/>
                    <input className="hidden" name="group_by" value={"time(" + this.state.aggregation + "s)"}/>
                    <input className="hidden" name="starttime" value={this.state.startDate}/>
                    <input className="hidden" name="endtime" value={this.state.endDate}/>
                </form>
            )
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


                    </Form>
                </Row>
                <Row>
                    <Col xs={12}>
                        {action}
                    </Col>
                </Row>
                <div style={{'overflowX': 'auto'}}>
                    {table}
                </div>

            </div>

        )
    }
}

