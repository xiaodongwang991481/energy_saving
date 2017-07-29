export function changeLoadingState(loading){
    return{
        type : "UTIL_CHANGE_LOADING_STATUS",
        payload:loading
    }
}