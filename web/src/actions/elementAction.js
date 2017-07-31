
export function showTimeSelectDialog(param) {
    return {
        type : "ELEMENT_SHOW_TIME_SELECT",
        payload : param
    }
}

export function hideTimeSelectDialog() {
    return {
        type : "ELEMENT_HIDE_TIME_SELECT",
    }
}