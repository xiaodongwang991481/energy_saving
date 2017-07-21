import React from "react"
import {connect} from "react-redux"
import {getModelList}  from "../actions/modelAction"
import {Table,tbody} from "react-bootstrap"
import axios from "axios"
import http from '../util/http'


@connect((store)=>{
    return {
        models:store.model.list
    }
})
export default class ModelList extends React.Component {
    constructor(props){
        super(props);
    }

    componentWillMount(){
        this.props.dispatch(getModelList());
    }


    uploadFile(name,event){
        console.log(event.target.files[0]);
        var data = new FormData();
        data.append('file', event.target.files[0]);
        axios.post(http.urlFormat(http.url.MODEL_IMPORT.url,name) ,data).then(function(item){
            alert("upload success");
        })
    }

    render(){

        let keys = [];
        if(this.props.models){
            keys = Object.keys(this.props.models);
            keys.sort();
        }
        let self = this;

        return(<div>

            <Table striped bordered condensed hover>
                <thead>
                <tr>
                    <th>Name</th>
                    <th>Atribute</th>
                    <th>Operation</th>
                </tr>
                </thead>
                <tbody>
                {
                    keys.map(function(item,index){
                        return (
                        <tr key={index}>
                            <td>{item}</td>
                            <td>
                                {
                                    self.props.models[item].map(function(attr,index){
                                        return(
                                            <div key={index}>{attr}</div>
                                        )
                                    })
                                }
                            </td>
                            <td>
                                <label className="btn btn-primary">
                                    Browse <input type="file" className="hidden" onChange={self.uploadFile.bind(this,item)} />
                                </label>
                            </td>
                        </tr>
                        );
                    })
                }
                </tbody>
            </Table>


        </div>);
    }
}