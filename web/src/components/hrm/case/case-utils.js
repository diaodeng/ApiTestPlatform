import {ElMessageBox} from "element-plus";
import {CaseStepTypeEnum, HrmDataTypeEnum} from "@/components/hrm/enum.js";
import {initStepData, initWebsocketData, initApiFormData} from "@/components/hrm/data-template.js";
import {randomString} from "@/utils/tools.js";


export function getStepDataByType(stepType) {
    if (!stepType) {
        ElMessageBox.alert("参数错误", "错误提示", {type: "error"});
        return;
    }
    if (stepType !== CaseStepTypeEnum.http && stepType !== CaseStepTypeEnum.websocket) {
        ElMessageBox.alert("不支持的测试步骤类型", "错误提示", {type: "error"});
        return;
    }
    let tapData = initStepData;
    if (stepType === CaseStepTypeEnum.http) {
        tapData = JSON.parse(JSON.stringify(initStepData));
    } else if (stepType === CaseStepTypeEnum.websocket) {
        let stepData = JSON.parse(JSON.stringify(initStepData));
        stepData.request = initWebsocketData;
        tapData = stepData;
    } else {
        return {};
    }
    tapData.step_id = randomString(10);

    tapData.step_type = stepType;
    return tapData;
}


export function getApiFormDataByType(apiType) {

    let apiFormData = initApiFormData;
    apiFormData = JSON.parse(JSON.stringify(initApiFormData));
    apiFormData.requestInfo.teststeps[0].request = getStepDataByType(apiType);
    apiFormData.requestInfo.teststeps[0].step_type = apiType;
    apiFormData.type = HrmDataTypeEnum.api;
    apiFormData.apiType = apiType;
    return apiFormData;
}