import {randomString} from "@/utils/tools.js";


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


export const initCaseFormData = {
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
        base_url: ""
    },
    teststeps: [initStepData]

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


