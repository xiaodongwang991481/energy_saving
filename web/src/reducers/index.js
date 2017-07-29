/**
 * Created by su on 6/7/17.
 */
import{ combineReducers } from "redux"
import model from "./modelReducer"
import util from "./utilReducer"


export default combineReducers(
    {
        model,
        util
    }
)


