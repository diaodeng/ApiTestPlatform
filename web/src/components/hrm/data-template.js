import {randomNumber, randomString} from "@/utils/tools.js";
import {
    HrmDataTypeEnum,
    CaseStepTypeEnum,
    CodeTypeEnum,
    CaseRunStatusEnum,
    RunTypeEnum, StatusNewEnum, MockTypeEnum
} from "@/components/hrm/enum.js";


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
    data: "",

    json: "",
    params: [],
    dataType: "",
    method: "GET",
}


/*
* 测试步骤数据模板，默认是http请求
* */
export const initStepData =
    {
        step_type: CaseStepTypeEnum.http,
        step_id: `${randomString(10)}`,
        enable: true,
        run_condition: {
            isRunInfo: {
                enable: false,
                conditionSource: "",
                loopVar: "",
                sourceType: ""
            },
            loopRunInfo: {
                enable: false,
                conditionSource: 1,
                loopVar: "",
                sourceType: ""
            },
        },
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
        setup_hooks: {functions: [], codeInfo: {codeType: CodeTypeEnum.js.value, codeContent: ""}},
        teardown_hooks: {functions: [], codeInfo: {codeType: CodeTypeEnum.js.value, codeContent: ""}},
        result: {response: {}, logs: {}, status: CaseRunStatusEnum.passed.value},
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
        setup_hooks: {functions: [], codeInfo: {codeType: CodeTypeEnum.js.value, codeContent: ""}},
        teardown_hooks: {functions: [], codeInfo: {codeType: CodeTypeEnum.js.value, codeContent: ""}},
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
    apiId: randomNumber(10),
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
* 转发规则组对应字段
* */
export const initForwardRulesFormData = {
    ruleId: undefined,
    ruleName: "新增转发规则组",
    originUrl: undefined,
    targetUrl: undefined,
    orderNum: 0,
    status: 2,
    simpleDesc: undefined,
    delFlag: 1,
}

/*
* 转发规则对应字段
* */
export const initForwardRulesDetailFormData = {
    ruleId: undefined,
    ruleDetailId: undefined,
    ruleDetailName: "新增转发规则详情记录",
    originUrl: undefined,
    targetUrl: undefined,
    orderNum: 0,
    status: 2,
    simpleDesc: undefined,
    delFlag: 1,
    matchType: 1
}

/*
* 转发规则对应字段
* */
export const initAgentFormData = {
    agentId: undefined,
    agentName: "新增转发规则组",
    agentCode: undefined,
    onlineTime: undefined,
    offlineTime: undefined,
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


export const initRunConfig = {
    userName: "",
    userId: null,
    env: null,
    ids: [],
    runType: RunTypeEnum.case,
    reportName: null,
    isAsync: false,
    repeatNum: 1,
    concurrent: 1,
    push: false,
    forwardConfig: {
        forward: false,
        agentId: undefined,
        forwardRuleIds: [],
    },
    runBySort: false
}


export const initMockRuleFormData = {
    name: '',
    projectId: null,
    path: '',
    method: 'GET',
    priority: 1,
    type: 2,
    status: StatusNewEnum.normal.value,
    mockType: MockTypeEnum.only_response.value,
    ruleCondition: [{
        source: 'query',
        key: '',
        operator: '=',
        value: '',
        data_type: 'str'
    }],
    response: {
        id: null,
        ruleResponseId: null,
        responseTag: '',
        responseCondition: [{
            source: 'query',
            key: '',
            operator: '=',
            value: '',
            data_type: 'str'
        }],
        statusCode: 200,
        headersTemplate: [{key: 'Content-Type', value: 'application/json'}],
        bodyTemplate: '{\n  "id": "{{uuid}}",\n  "name": "{{request.args.name}}",\n  "status": "active"\n}',
        delay: 0
    }
}



