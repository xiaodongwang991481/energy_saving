/**
 * Created by su on 6/7/17.
 */
import{ combineReducers } from "redux"
import model from "./modelReducer"
import util from "./utilReducer"
import element from "./elementReducer"
import task from "./taskReducer"


export default combineReducers(
    {
        model,
        util,
        element,
        task
    }
)


