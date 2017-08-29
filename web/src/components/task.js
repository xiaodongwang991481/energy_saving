import React from "react"
import {connect} from "react-redux"
import {getTaskList} from "../actions/taskAction"
import {Table} from "react-bootstrap"
import {Link} from "react-router-dom"

@connect(
    (store) => {
        return {
            taskList: store.task.task_list
        }
    }
)
export default class Task extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            dataCenter: "openlab"
        }
    }

    changeDataCenter(e) {
    }


    // showDetail(idx){
    //     if(this.props.taskList[idx]['status'] == 'success'){
    //         this.props.history.push('/task-detail/' + this.state.dataCenter + "/" + this.props.taskList[idx]['name']);
    //     }
    // }

    componentWillMount() {
        this.props.dispatch(getTaskList(this.state.dataCenter));
    }

    render() {
        let self =  this;
        return (<div>
                <select onChange={this.changeDataCenter.bind(this)} value={this.state.dataCenter}>
                    <option value="openlab" selected>openlab</option>
                </select>

                <Table striped bordered condensed hover>
                    <thead>
                    <tr>
                        <th>#</th>
                        <th>Name</th>
                        <th>Status</th>
                        <th>model</th>
                        <th>Statistics</th>
                    </tr>
                    </thead>
                    <tbody>
                    {
                        this.props.taskList.map(function (item, idx) {
                            let url = '/task-detail/' + self.state.dataCenter + "/" + self.props.taskList[idx]['name'];
                            if(item['properties'] && item['properties']['statistics'] && item['properties']['statistics']['controller_power_supply_attribute.power.total'])
                            {

                                let p = item['properties']['statistics']['controller_power_supply_attribute.power.total'];
                                let mse = p['MSE'];
                                let rsquare = p['rsquare'];
                                return (
                                    <tr key={idx} >
                                        <td>{idx}</td>
                                        <td><Link to={url}>{item['name']}</Link></td>
                                        <td>{item['status']}</td>
                                        <td>
                                            <div>{ item.properties ? item.properties.model : ""}</div>
                                            <div> {item.properties ? item.properties.model_type : ""}</div>
                                        </td>
                                        <td>
                                            <div>MSE : {mse}</div>
                                            <div>rsquare : {rsquare}</div>
                                        </td>
                                    </tr>
                                )
                            }
                            return (
                                <tr key={idx} >
                                    <td>{idx}</td>
                                    <td><Link to={url}>{item['name']}</Link></td>
                                    <td>{item['status']}</td>
                                    <td>
                                        <div>{ item.properties ? item.properties.model : ""}</div>
                                        <div> {item.properties ? item.properties.model_type : ""}</div>
                                    </td>
                                    <td></td>
                                </tr>
                            )
                        })
                    }

                    </tbody>
                </Table>
            </div>
        );
    }
}