import {randomString} from "@/utils/tools.js";
import {HrmDataTypeEnum, CaseStepTypeEnum} from "@/components/hrm/enum.js";


/*
* http请求模板
* */
export const initRequestData = {

    dataType: "",
    method: "GET",
    url: "",
    json: "",
    headers: [],
    params: [],
    data: []

}

/*
* websocket请求模板
* */
export const initWebsocketData = {
    url: "",
    headers: [],
    data: ""
}


/*
* 测试步骤数据模板，默认是http请求
* */
export const initStepData =
    {
        step_type: CaseStepTypeEnum.http,
        step_id: `${randomString(10)}`,
        name: "新增测试步骤",
        request: initRequestData,
        include: {
            config: {
                id: null,
                name: "",
                allow_extend: true
            }
        },
        think_time: {
            strategy: "",
            limit: 0
        },
        time_out: {
            enable: false,
            limit: 0
        },
        retry: {
            enable: false,
            limit: 0,
            delay: 0
        },
        validate: [],
        extract: [],
        variables: [],
        setup_hooks: [],
        teardown_hooks: [],
        result: {response: {}, logs: {}},
    }


export const initCaseRequestData = {
    config: {
        think_time: {
            strategy: "",
            limit: 0
        },
        time_out: {
          enable: false,
          limit: 0
        },
        retry: {
            enable: false,
            limit: 0,
            delay: 0
        },
        setup_hooks: [],
        teardown_hooks: [],
        variables: [],
        headers: [],
        parameters: [],
        base_url: "",
        include: {
            config: {
                id: null,
                name: "",
                allow_extend: true
            }
        },
        result: {response: {}, logs: {}}
    },
    teststeps: [initStepData]

}

/*
* 用例表request字段对应的数据
* */
export const initCaseFormData = {
    caseId: undefined,
    moduleId: undefined,
    projectId: undefined,
    caseName: "新增测试用例",
    notes: undefined,
    sort: 0,
    status: 2,
    remark: undefined,
    type: HrmDataTypeEnum.case,
    include: {},
    request: initCaseRequestData
}



/*
* API库表对应数据模板
* */
export const initApiFormData = {
    apiId: randomString(10),
    name: "新增API",
    path: "",
    interface: "",
    type: HrmDataTypeEnum.api,
    requestInfo: initCaseRequestData,
    parentId: undefined,
    isNew: true,
    stepType: CaseStepTypeEnum.http,
}


/*
* 转发规则对应字段
* */
export const initForwardRulesFormData = {
    ruleId: undefined,
    ruleName: "新增转发规则",
    originUrl: [""],
    targetUrl: undefined,
    orderNum: 0,
    status: 2,
    simpleDesc: undefined,
    delFlag: 1,
}


export const initDebugTalkFormData = {
    debugtalk: "def setup():" +
        "pass" +
        "" +
        "" +
        "" +
        "" +
        "def tearndown():" +
        "pass" +
        "" +
        "" +
        ""
}




