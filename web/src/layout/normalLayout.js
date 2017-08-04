import React from "react"
import {Navbar, Nav, NavItem, NavDropdown, MenuItem, Col, Row,Image} from "react-bootstrap"
import {Route, Switch} from "react-router-dom"
import ModelList from "../components/model-list"
import {LinkContainer} from "react-router-bootstrap"
import NotFound from "../components/noFound"
import MeasurementList from "../components/measurement-list"
import ShowData from "../components/show-data"
import {connect} from "react-redux"
import Action from "../components/action"
import TimeSelectDialog from "../components/element/timeSelectDialog"
import DeviceTypeDetail from "../components/deviceTypeDetail"
import MeasurementDetail from "../components/measurementDetail"
import DeviceDetail from "../components/deviceDetail"

const loadingImage = require("../images/loading.gif");

@connect((store)=>{
    return {
        loading : store.util.loading
    }
})
export default class NormalLayout extends React.Component {
    constructor(props) {
        super(props);
    }

    render() {

        let loading = "";
        if(this.props.loading){
            loading = (<Image className="loading" src={loadingImage} responsive ></Image>);
        }

        return (
            <div>
                <TimeSelectDialog/>
                <Navbar>
                    <Navbar.Header>
                        <Navbar.Brand>
                            {loading}
                            Energy Saving
                        </Navbar.Brand>
                    </Navbar.Header>
                    <Nav>
                        <LinkContainer to={"/model-list"}><NavItem eventKey={1}
                                                                   href="javascript:void(0);">Models</NavItem></LinkContainer>
                        <LinkContainer to={"/measurement-list"}><NavItem eventKey={2} href="javascript:void(0);">Measurement</NavItem></LinkContainer>
                        <LinkContainer to={"/action"}><NavItem eventKey={3} href="javascript:void(0);">Action</NavItem></LinkContainer>
                        {/*<NavDropdown eventKey={3} title="Dropdown" id="basic-nav-dropdown">*/}
                            {/*<MenuItem eventKey={3.1}>Action</MenuItem>*/}
                            {/*<MenuItem eventKey={3.2}>Another action</MenuItem>*/}
                            {/*<MenuItem eventKey={3.3}>Something else here</MenuItem>*/}
                            {/*<MenuItem divider/>*/}
                            {/*<MenuItem eventKey={3.4}>Separated link</MenuItem>*/}
                        {/*</NavDropdown>*/}
                    </Nav>
                </Navbar>
                <Switch>
                    <Route path="/show-data/:data_center/:device_type/:measurement?/:device?" component={ShowData}/>
                    {/*<Route path="/show-data/:data_center/:device_type/" component={DeviceTypeDetail}/>*/}
                    {/*<Route path="/show-data/:data_center/:device_type/measurement" component={MeasurementDetail}/>*/}

                    <div className="container">
                        <Row>
                            <Col md={1} lg={2}></Col>
                            <Col md={10} lg={8}>
                                <Route path="/model-list" component={ModelList}/>
                                <Route path="/measurement-list" component={MeasurementList}/>
                                <Route path="/action" component={Action}/>
                            </Col>
                        </Row>
                    </div>
                    <Route component={NotFound}/>
                </Switch>
            </div>
        )
    }
}
