import React from "react"
import {Button, Table, Form, FormGroup, FormControl, Row, Col, ControlLabel} from "react-bootstrap"
import {connect} from "react-redux"
import {getMeasurementData, getDeviceData, cleanDeviceData, cleanMeasurementData} from "../actions/modelAction"


@connect((store) => {
    return {
        measurement_data: store.model.measurement_data,
        device_data: store.model.device_data
    }
})
export default class ShowData extends React.Component {
    constructor(props) {
        super(props)
        this.isDevice = false;
        if (this.props.match.params['device']) {
            this.isDevice = true;
        }

        var date = new Date();
        var state = {};
        // state.startDate = date.toISOString().split("T")[0];
        // date.setDate(date.getDate() - 1);
        // state.endDate = date.toISOString().split("T")[0];
        state.startDate = "2017-07-05";
        state.endDate = "2017-07-06";
        state.aggregation = 300;
        this.state = state;

    }

    componentWillMount() {
        this.props.dispatch(cleanDeviceData());
        this.props.dispatch(cleanMeasurementData());
        this.refreshData();
    }

    refreshData() {
        var param = Object.assign({}, this.props.match.params, this.state);
        param['startDate'] += "T00:00:00";
        param['endDate'] += "T23:59:59";
        if (this.isDevice) {
            this.props.dispatch(getDeviceData(param));
        } else {
            this.props.dispatch(getMeasurementData(param));
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

    render() {
        let data = this.props.measurement_data.data;
        if (this.isDevice) {
            data = this.props.device_data.data;
        }

        let date = Object.keys(data);
        date.sort(function (a, b) {
            return (+new Date(a)) - (new Date(b));
        });

        let keyMap = {};
        for (var dateStr in data) {
            for (var key in data[dateStr]) {
                if (!keyMap[key]) {
                    keyMap[key] = 0;
                }
            }
        }
        let keys = Object.keys(keyMap);

        let table = "";
        if (this.isDevice) {
            table = (
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
                </Table>
            )
        } else {
            table = (
                <Table striped bordered condensed hover>
                    <thead>
                    <tr>
                        <th>Date</th>
                        {
                            keys.map(function (name, idx) {
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
                                    keys.map(function (key, idxC) {
                                        let val = data[dateStr][key] !== undefined ? data[dateStr][key] : "-"
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

        return (

            <div className="mb-20 ml-20 mr-20">
                <Row>
                    <Form  >
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

                        <Col xs={3}>
                            <Button className="mt-25" onClick={this.search.bind(this)}>
                                Search
                            </Button>
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

