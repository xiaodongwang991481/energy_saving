import React from "react"
import {Navbar,Nav,NavItem,NavDropdown,MenuItem,Col,Row} from "react-bootstrap"
import {Route,Switch} from "react-router-dom"
import ModelList from "../components/model-list"
import {LinkContainer} from "react-router-bootstrap"
import NotFound from "../components/noFound"
import MeasurementList from "../components/measurement-list"
import ShowData from "../components/show-data"

export default class NormalLayout extends React.Component{
    constructor(props){
        super(props);

    }

    render(){
        return (
            <div>
                <Navbar>
                    <Navbar.Header>
                        <Navbar.Brand>
                            <a href="#">React-Bootstrap</a>
                        </Navbar.Brand>
                    </Navbar.Header>
                    <Nav>
                        <LinkContainer to={"/model-list"}><NavItem eventKey={1} href="javascript:void(0);">Models</NavItem></LinkContainer>
                        <LinkContainer to={"/measurement-list"}><NavItem eventKey={2} href="javascript:void(0);">Measurement</NavItem></LinkContainer>
                        <NavDropdown eventKey={3} title="Dropdown" id="basic-nav-dropdown">
                            <MenuItem eventKey={3.1}>Action</MenuItem>
                            <MenuItem eventKey={3.2}>Another action</MenuItem>
                            <MenuItem eventKey={3.3}>Something else here</MenuItem>
                            <MenuItem divider />
                            <MenuItem eventKey={3.4}>Separated link</MenuItem>
                        </NavDropdown>
                    </Nav>
                </Navbar>
                <div className="container">
                    <Row>
                        <Col md={1} lg={2}></Col>
                        <Col md={10} lg={8}>
                            <Switch>
                                <Route path="/model-list" component={ModelList}/>
                                <Route path="/measurement-list" component={MeasurementList} />
                                <Route path="/show-data/:data_center/:device_type/:measurement/:device?" component={ShowData}/>
                                <Route component={NotFound}/>
                            </Switch>
                        </Col>
                    </Row>
                </div>
            </div>
        )
    }
}
