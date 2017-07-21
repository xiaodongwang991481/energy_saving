import React from "react"
import {connect} from "react-redux"
import {getMeasurementData} from "../actions/modelAction"
import {getDeviceData} from "../actions/modelAction"



@connect((store)=>{
    return{
        data : store.model.data
    }
})
export default class ShowData extends React.Component {
    constructor(props){
        super(props)
    }

    componentWillMount(){
        if(this.props.match['device']){
            this.props.dispatch(getDeviceData(this.props.match.params));
        }else{
            this.props.dispatch(getMeasurementData(this.props.match.params));
        }
    }

    render(){
        return (
            <div>
                show all data
            </div>
        )
    }
}

