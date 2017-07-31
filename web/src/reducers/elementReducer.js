export default function reducer(state={
    time_select : {
        show : false,
        start_time:"",
        end_time:"",
        callback:null
    }
},action){
    switch (action.type) {
        case "ELEMENT_SHOW_TIME_SELECT":
            let obj = Object.assign({},state.time_select,action.payload,{show:true});
            return{
                ...state,
                time_select : obj
            }
        case "ELEMENT_HIDE_TIME_SELECT":
            var newTimeObj = {
                show : false,
                start_time:"",
                end_time:"",
                callback:null
            }
            return{
                ...state,
                time_select:newTimeObj
            }
        default:
            return state;
    }
}


