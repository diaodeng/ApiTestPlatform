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
    urlEqual: {label: "URL相等", value:1},
    urlNotEqual: {label: "URL不相等", value:2},
    urlContain: {label: "URL包含", value:4},
    hostEqual: {label: "HOST相等", value:8},
    hostNotEqual: {label: "HOST不相等", value:16},
    hostContain: {label: "HOST包含", value:32},
    pathEqual: {label: "PATH相等", value:64},
    pathNotEqual: {label: "PATH不相等", value:128},
    pathContain: {label: "PATH包含", value:256}
}

export const ForwardReplaceContentEnum = {
    url: {label: "URL", value:1},
    host: {label: "HOST", value:2},
    PATH: {label: "PATH", value:4},
    ORIGIN: {label: "ORIGIN", value:8},
}


export const DelFlagNewEnum = {
    normal :{label: "normal", value:1},
    delete: {label: "delete", value:2},
}

export const StatusNewEnum = {
    disabled :{label: "禁用", value:1, elTagType: "danger"},
    normal: {label: "正常", value:2, elTagType: "primary"},
}

export const AgentStatusEnum = {
    disabled :{label: "离线", value:1, elTagType: "danger"},
    normal: {label: "在线", value:2, elTagType: "success"},
}


/*
* 作用范围
* */
export const ScopeEnum = {
    global: {label: "全局", value:1, elTagType: "success"},
    project :{label: "项目", value:2, elTagType: "danger"},
    module: {label: "模块", value:4, elTagType: "success"},
    case: {label: "用例", value:8, elTagType: "success"},

}


/*
* 自定义脚本类型
* */
export const CodeTypeEnum = {
    python: {label: "python", value:1, elTagType: "primary"},
    js :{label: "js", value:2, elTagType: "primary"},


}

/*
* 断言实际值取值方式
* */
export const AssertOriginalEnum = {
    expression: {label: "表达式", value:1, elTagType: "primary"},
    original :{label: "原始值", value:2, elTagType: "primary"},
}

export const CaseRunStatusEnum = {
    passed: {label: "成功", value:1, elTagType: "primary"},
    failed :{label: "失败", value:2, elTagType: "primary"},
    skipped :{label: "跳过", value:3, elTagType: "primary"},
    // deselected :{label: "原始值", value:4, elTagType: "primary"},
    xfailed :{label: "标记失败", value:5, elTagType: "primary"},
    xpassed :{label: "标记成功", value:6, elTagType: "primary"},
    warnings :{label: "警告", value:7, elTagType: "primary"},
    error :{label: "错误", value:8, elTagType: "primary"},
}

export const MockTypeEnum = {
    only_response: {label: "仅响应", value:1, elTagType: "primary"},
    only_request: {label: "仅请求", value:2, elTagType: "primary"},
    request_and_response: {label: "请求和响应", value:3, elTagType: "primary"},
    not_mock: {label: "原始请求", value:4, elTagType: "primary"},
}

