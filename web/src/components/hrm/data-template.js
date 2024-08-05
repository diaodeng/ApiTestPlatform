import {randomString} from "@/utils/tools.js";
import {HrmDataTypeEnum} from "@/components/hrm/enum.js";


export const initRequestData = {

    dataType: "",
    method: "GET",
    url: "",
    json: {},
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
        step_type: 1,
        step_id: `${randomString(10)}`,
        name: "新增测试步骤",
        request: initRequestData,
        include: {
            config: {
                id: "",
                name: ""
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
        teardown_hooks: []
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
            configId: null
        }
    },
    teststeps: [initStepData]

}

export const initCaseFormData = {
  caseId: undefined,
  moduleId: undefined,
  projectId: undefined,
  caseName: undefined,
  notes: undefined,
  sort: 0,
  status: "0",
  remark: undefined,
  type: HrmDataTypeEnum.case,
  include: {},
  request: initCaseRequestData
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


