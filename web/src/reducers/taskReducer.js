export default function reducer(state = {
    task_list: [],
    task_detail: {},
    task_model_list:{}
}, action) {
    switch (action.type) {
        case "TASK_GET_TASK_LIST":
            return {
                ...state,
                task_list: action.payload
            }
        case "TASK_GET_TASK_RESULT":
            let detail = Object.assign({}, state.task_detail, action.payload);
            return {
                ...state,
                task_detail: detail
            }
        case "TASK_GET_TASK_RESULT_PREDICTION":
            detail = Object.assign({}, state.task_detail);
            detail.prediction = action.payload;
            return {
                ...state,
                task_detail: detail
            }
        case "TASK_GET_TASK_RESULT_EXPECTATION":
            detail = Object.assign({}, state.task_detail);
            detail.expectation = action.payload;
            return {
                ...state,
                task_detail: detail
            }
        case "TASK_CLEAR_TASK_RESULT":
            return {
                ...state,
                task_detail: {}
            }
        case "TASK_GET_TASK_RESULT_MODEL_LIST":
            return {
                ...state,
                task_model_list : action.payload
            }
        default:
            return state;
    }
}


