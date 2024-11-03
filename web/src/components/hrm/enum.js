export const runDetailViewTypeEnum = {
    "case": 1,
    "report": 2,
    "api": 3,
}


export const RunTypeEnum = {
    case: 1,
    module: 2,
    suite: 4,
    project: 8,
    api: 16,
    case_debug: 32,
}


export const HrmDataTypeEnum = {
    project: 1,
    module: 2,
    case: 3,
    config: 4,
    suite: 5,
    report: 6,
    env: 7,
    debugtalk: 8,
    task: 9,
    api: 10,
    folder: 11,
    suite_detail: 12,
    suite_case_list: 13,
    run_detail: 14,
    api_http: 15,
    api_websocket: 16,
}


/*
* 测试步骤的type与api的type一样（一个api只能有一个步骤）
* */
export const CaseStepTypeEnum = {
    http: 1,
    websocket: 2,
    webui: 3,
    folder: 4,
}

export const EditTableContextMenuEnum = {
    InsertRowBefore: 1,
    InsertRowAfter: 2,
    edit: 3,
    InsertColumnBefore: 4,
    InsertColumnAfter: 5,
    DeleteRow: 6,
    DeleteColumn: 7,
    HideColumn: 8,
    editHeader: 9,
    editCell: 10,
}


export const ForwardRuleMatchTypeEnum = {
    urlEqual: {name: "URL相等", value:1},
    urlNotEqual: {name: "Url不相等", value:2},
    urlContain: {name: "Url包含", value:4},
    hostEqual: {name: "HOST相等", value:8},
    hostNotEqual: {name: "HOST不相等", value:16},
    hostContain: {name: "HOST包含", value:32},
    pathEqual: {name: "PATH相等", value:64},
    pathNotEqual: {name: "PATH不相等", value:128},
    pathContain: {name: "PATH包含", value:256}
}


export const DelFlagNewEnum = {
    normal :{name: "normal", value:1},
    delete: {name: "delete", value:2},
}

export const StatusNewEnum = {
    disabled :{name: "disabled", value:1},
    normal: {name: "normal", value:2},
}
