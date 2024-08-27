import {randomString} from "@/utils/tools.js";
import {HrmDataTypeEnum, CaseStepTypeEnum} from "@/components/hrm/enum.js";


export const initRequestData = {

    dataType: "",
    method: "GET",
    url: "",
    json: "",
    headers: [],
    params: [],
    data: []

}

export const initWebsocketData = {
    url: "",
    headers: [],
    data: ""
}

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
        validate: [],
        extract: [],
        variables: [],
        setup_hooks: [],
        teardown_hooks: [],
        result: {response: {}, logs: {}},
    }


    /*
    * 用例表request字段对应的数据
    * */
export const initCaseRequestData = {
    config: {
        think_time: {
            strategy: "",
            limit: 0
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

export const initCaseFormData = {
  caseId: undefined,
  moduleId: undefined,
  projectId: undefined,
  caseName: "新增测试用例",
  notes: undefined,
  sort: 0,
  status: "0",
  remark: undefined,
  type: HrmDataTypeEnum.case,
  include: {},
  request: initCaseRequestData
}


export const initApiFormData = {
    apiId: randomString(10),
    name: "新增API",
    path: "",
    interface: "",
    type: HrmDataTypeEnum.api,
    requestInfo: initCaseRequestData
}

export const initDebugTalkFormData ={
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




