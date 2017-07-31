import React from "react"
import {connect} from "react-redux"
import {getAllModelTypes} from "../actions/modelAction"
import {Table,Button} from "react-bootstrap"
import axios from "axios"
import http from "../util/http"
import {showTimeSelectDialog} from "../actions/elementAction"


@connect(
    (store)=>{
        return {model_types : store.model.model_types};
    }
)
export default class Action extends React.Component {
    constructor(props){
        super(props);
    }

    componentWillMount(){
        this.props.dispatch(getAllModelTypes("openlab"));
    }

    buildModel(modelName){
        axios.post(http.urlFormat(http.url.MODEL_BUILD_MODEL.url,'openlab',modelName)).then(function(res){
            alert("server start build !");
        })
    }


    trainModel(modelName){
        this.props.dispatch(showTimeSelectDialog({callback : this.callback.bind(this,'train',modelName)}));
    }

    testModel(modelName){
        this.props.dispatch(showTimeSelectDialog({callback : this.callback.bind(this,'test',modelName)}));
    }

    callback(type,modelName,param){
        var data = {
            starttime:param['start_time'],
            endtime:param['end_time'],
        }
        if(type == 'train'){
            axios.post(http.urlFormat(http.url.MODEL_TRAIN_MODEL.url,'openlab',modelName),data).then(function(){
               alert("add train job success !");
            });
        }else if(type=='apply'){
            axios.post(http.urlFormat(http.url.MODEL_APPLY_MODEL.url,"openlab",modelName),data).then(function(){
                alert("apply success");
            })
        } else{
            axios.post(http.urlFormat(http.url.MODEL_TEST_MODEL.url,'openlab',modelName),data).then(function(){
                alert("add test job success !");
            });
        }
    }

    applyModel(modelName){
        this.props.dispatch(showTimeSelectDialog({callback : this.callback.bind(this,'apply',modelName)}));

    }



    render(){
        var data = this.props.model_types;
        var self = this;
        return(
            <div>
                <Table striped bordered condensed hover>
                    <thead>
                    <tr>
                        <th>Name</th>
                        <th>Operation</th>
                    </tr>
                    </thead>
                    <tbody>
                    {
                        data.map(function (item,idx) {
                            return(
                                <tr key={idx}>
                                    <td>
                                        {item}
                                    </td>
                                    <td>
                                        <Button className="mr-10 ml-10" onClick={self.buildModel.bind(self,item)}>build</Button>
                                        <Button className="mr-10 ml-10" bsStyle="primary" onClick={self.trainModel.bind(self,item)}>train</Button>
                                        <Button className="mr-10 ml-10" bsStyle="success" onClick={self.testModel.bind(self,item)}>test</Button>
                                        <Button className="mr-10 ml-10" bsStyle="info" onClick={self.applyModel.bind(self,item)}> apply</Button>

                                    </td>
                                </tr>
                            );
                        })
                    }
                    </tbody>
                </Table>
            </div>
        )
    }
}