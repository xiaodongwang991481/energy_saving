import React from "react"

export default class DeviceTypeDetail extends React.Component {
    constructor(props){
        super(props);
        var state = {};
        state.startDate = "2017-07-05";
        state.endDate = "2017-07-06";
        state.aggregation = 300;
        state.aggregation_type = "mean";
        this.state = state;
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

    render(){
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