export default function reducer(state={
    loading:false
},action){
    switch (action.type) {
        case "UTIL_CHANGE_LOADING_STATUS":
            return{
                ...state,
                loading : action.payload
            }
        default:
            return state;
    }
}


