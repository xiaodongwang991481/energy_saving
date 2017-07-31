import React from "react"
import {connect} from "react-redux"
import {Modal,Button,FormGroup,ControlLabel,Form,FormControl,Col} from "react-bootstrap"
import {hideTimeSelectDialog} from "../../actions/elementAction"


@connect(
    (store)=>{
        return{
            time_select : store.element.time_select
        }
    }
)
export default class TimeSelectDialog extends React.Component{
    constructor(props){
        super(props);
        this.state = {
            start_time:"",
            end_time : ""
        }
    }


    onChange(event){
        var target = event.target;
        var name = target.name;
        var value = target.value;
        this.setState({[name]:value});
    }
    submit(){
        var param = Object.assign({},this.state);
        if(this.props.time_select.callback){
            this.props.time_select.callback(param);
        }
        this.props.dispatch(hideTimeSelectDialog());
    }

    close(){
        this.props.dispatch(hideTimeSelectDialog());
        this.setState({start_time:"", end_time : ""});
    }

    render(){
        return (
            <div className="static-modal" >
                <Modal show={this.props.time_select.show} >
                    <Modal.Header>
                        <Modal.Title>Select Time</Modal.Title>
                    </Modal.Header>

                    <Modal.Body>
                        <Form horizontal onSubmit={this.submit.bind(this)}>
                            <FormGroup controlId="start_time">
                                <Col componentClass={ControlLabel} sm={2}>
                                    Start Time
                                </Col>
                                <Col sm={10}>
                                    <FormControl type="datetime-local" name="start_time" onChange={this.onChange.bind(this)} />
                                </Col>
                            </FormGroup>

                            <FormGroup controlId="end_time">
                                <Col componentClass={ControlLabel} sm={2}>
                                    End Time
                                </Col>
                                <Col sm={10}>
                                    <FormControl type="datetime-local" name="end_time" onChange={this.onChange.bind(this)} />
                                </Col>
                            </FormGroup>

                        </Form>

                    </Modal.Body>

                    <Modal.Footer>
                        <Button onClick={this.close.bind(this)}>Cancel</Button>
                        <Button bsStyle="primary" onClick={this.submit.bind(this)}>Ok</Button>
                    </Modal.Footer>

                </Modal>
            </div>
        )
    }
}