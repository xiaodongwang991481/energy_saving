import React from "react";
import {getTaskResult, getTaskResultExpectation, getTaskResultPrediction, clearTaskDetail,getTaskDetailByDevice,getTaskResultModeList} from "../actions/taskAction"
import {getMeasurementList} from "../actions/modelAction"
import {connect} from "react-redux"
import HighCharts from "./element/highCharts"
import {Form, FormControl, Row, Col, FormGroup, ControlLabel, Button} from "react-bootstrap"

@connect(
    (store) => {
        return {
            taskDetail: store.task.task_detail,
            measurementList: store.task.task_model_list
        }
    }
)
export default class TaskDetail extends React.Component {
    constructor(props) {
        super(props);
        this.dataCenter = this.props.match.params['data_center'];
        this.resultId = this.props.match.params['result_id'];
        this.state = {};
    }

    componentWillMount() {
        this.props.dispatch(getTaskResultModeList(this.dataCenter, this.resultId));
        // this.props.dispatch(getTaskResultExpectation(this.dataCenter, this.resultId));
        // this.props.dispatch(getTaskResultPrediction(this.dataCenter, this.resultId));
        this.props.dispatch(getMeasurementList());
    }

    componentWillUnmount() {
        this.props.dispatch(clearTaskDetail());
    }

    formatData(data) {
        let date = Object.keys(data);
        date.sort((a, b) => {
            return +(new Date(a)) - (new Date(b));
        });

        let res = [];
        date.forEach(function (dateStr) {
            res.push([(+(new Date(dateStr))), data[dateStr]]);
        })
        return res;
    }

    componentWillReceiveProps(nextProps) {
        if (this.props.measurementList != nextProps.measurementList) {
            this.setState(this.initSelect(nextProps.measurementList,{}, 0));
        }
    }

    initSelect(measurementMap,state,idx) {
        if (measurementMap) {

            let deviceType = state['deviceType'];
            let measurement = state['measurement'];
            switch (idx) {
                case 0:
                    let deviceTypeList = Object.keys(measurementMap['properties']['device_type_mapping']);
                    state['deviceTypeList'] = deviceTypeList;
                    state['deviceType'] = deviceTypeList[0];
                    deviceType = state['deviceType'];
                case 1:
                    let measurementList = Object.keys(measurementMap['properties']['device_type_mapping'][deviceType]);
                    state['measurementList'] = measurementList;
                    state['measurement'] = measurementList[0];
                    measurement = state['measurement'];
                case 2:
                    let deviceList = measurementMap['properties']['device_type_mapping'][deviceType][measurement];
                    state['deviceList'] = deviceList;
                    state['device'] = deviceList[0];
                default:
                    break;
            }
        }
        return state;
    }

    onChange(event) {
        var target = event.target;
        var name = target.name;
        var val = target.value;
        var state = Object.assign({},this.state,{[name] : val});
        if(name == 'deviceType'){
            state = this.initSelect(this.props.measurementList,state,1);
        }else if(name == 'measurement'){
            state = this.initSelect(this.props.measurementList,state,2);
        }
        this.setState(state);
    }

    onSubmit() {

    }

    updateChart(){
        this.props.dispatch(clearTaskDetail());

        this.props.dispatch(getTaskDetailByDevice(this.dataCenter,this.resultId,'prediction',this.state['deviceType'],this.state['measurement'],this.state['device']));
        this.props.dispatch(getTaskDetailByDevice(this.dataCenter,this.resultId,'expectation',this.state['deviceType'],this.state['measurement'],this.state['device']));
    }


    render() {

        let chart = null;
        if (this.props.taskDetail.prediction && this.props.taskDetail.expectation) {
            debugger
            let prediction = this.formatData(this.props.taskDetail.prediction);
            let expectation = this.formatData(this.props.taskDetail.expectation);
            let series = [
                {name: 'prediction', data: prediction},
                {name: 'expectation', data: expectation}
            ]
            chart = (
                <HighCharts series={series} title={this.resultId}/>
            );
        }


        let select = "";
        if (this.state.deviceTypeList && this.state.measurementList && this.state.deviceList) {

            select = (
                <Row>
                    <Form  >
                        <Col xs={3}>
                            <FormGroup controlId="data-type">
                                <ControlLabel>Data Center</ControlLabel>
                                <FormControl componentClass="select" name="deviceType"
                                             onChange={this.onChange.bind(this)}
                                             value={this.state.deviceType}>
                                    {
                                        this.state.deviceTypeList.map(function (type, idx) {
                                            return (
                                                <option value={type} key={idx}>{type}</option>
                                            )
                                        })
                                    }

                                </FormControl>
                            </FormGroup>
                        </Col>
                        <Col xs={3}>
                            <FormGroup controlId="measurement">
                                <ControlLabel>Device Type</ControlLabel>
                                <FormControl componentClass="select" name="measurement"
                                             onChange={this.onChange.bind(this)}
                                             value={this.state.measurement}>
                                    {
                                        this.state.measurementList.map(function(name,idx){
                                            return(
                                                <option value={name} key={idx} > {name}</option>
                                            )
                                        })
                                    }
                                </FormControl>
                            </FormGroup>
                        </Col>
                        <Col xs={3}>
                            <FormGroup controlId="device">
                                <ControlLabel>Device</ControlLabel>
                                <FormControl componentClass="select" name="device"
                                             onChange={this.onChange.bind(this)}
                                             value={this.state.device}>
                                    {
                                        this.state.deviceList.map(function(device,idx){
                                            return(
                                                <option value={device} key={idx} > {device}</option>
                                            )
                                        })
                                    }
                                </FormControl>
                            </FormGroup>
                        </Col>
                        <Col xs={3}>
                            <Button className="mt-25" onClick={this.updateChart.bind(this)}> search</Button>
                        </Col>

                    </Form>
                </Row>
            );
        }

        return (<div className="mt-20 ml-20 mr-20">

                {select}
                <div>Task Detail</div>
                {chart}
            </div>
        );
    }
}