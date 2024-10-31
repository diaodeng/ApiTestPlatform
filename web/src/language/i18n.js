//index.ts
import {createI18n} from "vue-i18n";

//en
const en = {
    message: {
        caseDetail: {
            tabNames: {
                configLabel: 'config',
                stepsLabel: 'config',

                message: "messages",
                headers: "headers",
                vph: "variables/parameters/hooks",
                vphc: "variables",  // 配置页面使用的
                other: "other",
                request: "request",
                ev: "extract/validate",
                vh: "variables/hooks",
            }
        },
        configTable: {
            header: {
                variables: "variables",
                parameters: "parameters",
                setup_hooks: "setup_hooks",
                teardown_hooks: "teardown_hooks",
                extract: "extract",
                validate: "validate",

                key: "key",
                value: "value",
                desc: "desc",
                check: "check",
                comparator: "Comparator",
                type: "type",
                expected: "expected",
                msg: "msg",
                enable: "enable"

            }
        },
        other: {
            thinktime: "thinktime(s)",
            timeout: "timeout(s)",
            retry: "retry"
        },
        button:{
            search:"Search",
            save: "Save",
            saveAndReturn: "Save & Return",
            debug: "Debug",
            reset: "Reset",
            refresh: "Refresh",
            add: "Add",
            modify: "Modify",
            delete: "Delete",
            export: "Export",
            import: "Import",
            run: "Run",

        },
        tableHeader: {
            caseId: "CaseId",
            caseName: "CaseName",
            belongProject: "BelongProject",
            belongModule: "BelongModule",
            status: "Status",
            creator: "Creator",
            creatTime: "CreatTime",
            updateTime: "UpdateTime",
            operate: "Operate"
        }

    }
}

//zh
const zh = {
    message: {
        caseDetail: {
            tabNames: {
                configLabel: '配置',
                stepsLabel: '测试步骤',
                message: "基本信息",
                headers: "请求头",
                vph: "变量/参数化/回调",
                vphc: "变量",
                other: "其他",
                request: "请求",
                ev: "抽取/断言",
                vh: "变量/回调",
            }
        },
        configTable: {
            header: {
                variables: "变量",
                parameters: "参数化",
                setup_hooks: "启动回调",
                teardown_hooks: "结束回调",
                extract: "抽取",
                validate: "断言",

                key: "键",
                value: "值",
                desc: "描述",
                check: "实际值",
                comparator: "对比方法",
                type: "类型",
                expected: "期望值",
                msg: "备注",
                enable: "启用"

            }
        },
        other: {
            thinktime: "思考时间(s)",
            timeout: "超时时间(s)",
            retry: "重试次数"
        }
    }
}

const i18n = createI18n({
    locale: localStorage.getItem('language') || 'zh', // 默认是中文
//   fallbackLocale: 'en', // 语言切换的时候是英文
    globalInjection: true,//全局配置$t
    legacy: false,//vue3写法
    messages: {en, zh}// 需要做国际化的语种,就是刚才编写的两个语言

})

export default i18n