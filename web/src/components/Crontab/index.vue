<template>
    <div>
        <el-tabs type="border-card">
            <el-tab-pane label="分钟" v-if="shouldHide('min')">
                <CrontabMin
                    @update="updateCrontabValue"
                    :check="checkNumber"
                    :cron="crontabValueObj"
                    ref="cronmin"
                />
            </el-tab-pane>

            <el-tab-pane label="小时" v-if="shouldHide('hour')">
                <CrontabHour
                    @update="updateCrontabValue"
                    :check="checkNumber"
                    :cron="crontabValueObj"
                    ref="cronhour"
                />
            </el-tab-pane>

            <el-tab-pane label="日" v-if="shouldHide('day')">
                <CrontabDay
                    @update="updateCrontabValue"
                    :check="checkNumber"
                    :cron="crontabValueObj"
                    ref="cronday"
                />
            </el-tab-pane>

            <el-tab-pane label="月" v-if="shouldHide('month')">
                <CrontabMonth
                    @update="updateCrontabValue"
                    :check="checkNumber"
                    :cron="crontabValueObj"
                    ref="cronmonth"
                />
            </el-tab-pane>

            <el-tab-pane label="周" v-if="shouldHide('week')">
                <CrontabWeek
                    @update="updateCrontabValue"
                    :check="checkNumber"
                    :cron="crontabValueObj"
                    ref="cronweek"
                />
            </el-tab-pane>
        </el-tabs>

        <div class="popup-main">
            <div class="popup-result">
                <p class="title">时间表达式</p>
                <table>
                    <thead>
                    <tr>
                        <th v-for="item of tabTitles" :key="item">{{item}}</th>
                        <th>Cron 表达式</th>
                    </tr>

                    </thead>
                    <tbody>
                    <tr>
                        <td>
                            <span v-if="crontabValueObj.min.length < 10">{{crontabValueObj.min}}</span>
                            <el-tooltip v-else :content="crontabValueObj.min" placement="top"><span>{{crontabValueObj.min}}</span></el-tooltip>
                        </td>
                        <td>
                            <span v-if="crontabValueObj.hour.length < 10">{{crontabValueObj.hour}}</span>
                            <el-tooltip v-else :content="crontabValueObj.hour" placement="top"><span>{{crontabValueObj.hour}}</span></el-tooltip>
                        </td>
                        <td>
                            <span v-if="crontabValueObj.day.length < 10">{{crontabValueObj.day}}</span>
                            <el-tooltip v-else :content="crontabValueObj.day" placement="top"><span>{{crontabValueObj.day}}</span></el-tooltip>
                        </td>
                        <td>
                            <span v-if="crontabValueObj.month.length < 10">{{crontabValueObj.month}}</span>
                            <el-tooltip v-else :content="crontabValueObj.month" placement="top"><span>{{crontabValueObj.month}}</span></el-tooltip>
                        </td>
                        <td>
                            <span v-if="crontabValueObj.week.length < 10">{{crontabValueObj.week}}</span>
                            <el-tooltip v-else :content="crontabValueObj.week" placement="top"><span>{{crontabValueObj.week}}</span></el-tooltip>
                        </td>
                        <td class="result">
                            <span v-if="crontabValueString.length < 90">{{crontabValueString}}</span>
                            <el-tooltip v-else :content="crontabValueString" placement="top"><span>{{crontabValueString}}</span></el-tooltip>
                        </td>
                    </tr>

                    </tbody>
                </table>
            </div>
            <CrontabResult :ex="crontabValueString"></CrontabResult>

            <div class="pop_btn">
                <el-button type="primary" @click="submitFill">确定</el-button>
                <el-button type="warning" @click="clearCron">重置</el-button>
                <el-button @click="hidePopup">取消</el-button>
            </div>
        </div>
    </div>
</template>

<script setup>
import CrontabMin from "./min.vue"
import CrontabHour from "./hour.vue"
import CrontabDay from "./day.vue"
import CrontabMonth from "./month.vue"
import CrontabWeek from "./week.vue"
import CrontabResult from "./result.vue"
const { proxy } = getCurrentInstance()
const emit = defineEmits(['hide', 'fill'])
const props = defineProps({
    hideComponent: {
        type: Array,
        default: () => [],
    },
    expression: {
        type: String,
        default: ""
    }
})
const tabTitles = ref(["分钟", "小时", "日", "月", "周"])
const hideComponent = ref([])
const expression = ref('')
const unsupportedTokenPattern = /[LW#]/
const crontabValueObj = ref({
    min: "*",
    hour: "*",
    day: "*",
    month: "*",
    week: "*",
})

function convertWeekTokenToCelery(token) {
    if (!/^\d+$/.test(token)) {
        return token
    }
    const num = Number(token)
    if (num === 0 || num === 7) {
        return "0"
    }
    if (num >= 1 && num <= 6) {
        return String(num - 1)
    }
    return token
}

function convertWeekTokenToUi(token) {
    if (!/^\d+$/.test(token)) {
        return token
    }
    const num = Number(token)
    if (num === 0 || num === 7) {
        return "1"
    }
    if (num >= 1 && num <= 6) {
        return String(num + 1)
    }
    return token
}

function normalizeWeekField(fieldValue, tokenConverter) {
    if (!fieldValue || fieldValue === "?") {
        return "*"
    }
    return fieldValue
        .split(",")
        .map((segment) => {
            const value = segment.trim()
            if (!value) {
                return value
            }
            if (value.includes("-")) {
                const [start, end] = value.split("-", 2).map((item) => tokenConverter(item.trim()))
                return `${start}-${end}`
            }
            if (value.includes("/")) {
                const [base, step] = value.split("/", 2)
                return `${tokenConverter(base.trim())}/${step.trim()}`
            }
            return tokenConverter(value)
        })
        .join(",")
}

const crontabValueString = computed(() => {
    const obj = crontabValueObj.value
    const dayValue = (obj.day || "*") === "?" ? "*" : (obj.day || "*")
    const weekValue = normalizeWeekField(obj.week || "*", convertWeekTokenToCelery)
    return `${obj.min || "*"} ${obj.hour || "*"} ${dayValue} ${obj.month || "*"} ${weekValue}`
})
watch(()=>expression.value, () => resolveExp())
function shouldHide(key) {
    return !(hideComponent.value && hideComponent.value.includes(key))
}
function resolveExp() {
    // 反解析 表达式
    if (!expression.value) {
        clearCron()
        return
    }

    const arr = expression.value.trim().split(/\s+/)
    if (arr.length === 5) {
        crontabValueObj.value = {
            min: arr[0] || "*",
            hour: arr[1] || "*",
            day: arr[2] || "*",
            month: arr[3] || "*",
            week: normalizeWeekField(arr[4] || "*", convertWeekTokenToUi)
        }
        return
    }
    if (arr.length >= 6) {
        // 兼容历史 Quartz 形式（秒 分 时 日 月 周 [年]）
        crontabValueObj.value = {
            min: arr[1] || "*",
            hour: arr[2] || "*",
            day: arr[3] || "*",
            month: arr[4] || "*",
            week: normalizeWeekField(arr[5] || "*", convertWeekTokenToUi)
        }
        return
    }
    clearCron()
}

// 由子组件触发，更改表达式组成的字段值
function updateCrontabValue(name, value, from) {
    console.log(name + ": " + value + ": " + from)
    crontabValueObj.value[name] = value
}
// 表单选项的子组件校验数字格式（通过-props传递）
function checkNumber(value, minLimit, maxLimit) {
    // 检查必须为整数
    value = Math.floor(value)
    if (value < minLimit) {
        value = minLimit
    } else if (value > maxLimit) {
        value = maxLimit
    }
    return value
}
// 隐藏弹窗
function hidePopup() {
    emit("hide")
}

function validateCeleryExpression() {
    const dayValue = crontabValueObj.value.day || "*"
    const weekValue = crontabValueObj.value.week || "*"
    if (unsupportedTokenPattern.test(dayValue)) {
        return "日字段不支持 L/W/#，请改用普通 cron 语法"
    }
    if (unsupportedTokenPattern.test(weekValue)) {
        return "周字段不支持 L/W/#，请改用普通 cron 语法"
    }
    return ""
}

// 填充表达式
function submitFill() {
    const validateMessage = validateCeleryExpression()
    if (validateMessage) {
        proxy.$modal.msgError(validateMessage)
        return
    }
    emit("fill", crontabValueString.value)
    hidePopup()
}

function clearCron() {
    // 还原选择项
    crontabValueObj.value = {
        min: "*",
        hour: "*",
        day: "*",
        month: "*",
        week: "*",
    }
}
onMounted(() => {
    expression.value = props.expression
    hideComponent.value = props.hideComponent
})
</script>

<style lang="scss" scoped>
.pop_btn {
    text-align: center;
    margin-top: 20px;
}
.popup-main {
    position: relative;
    margin: 10px auto;
    background: #fff;
    border-radius: 5px;
    font-size: 12px;
    overflow: hidden;
}
.popup-title {
    overflow: hidden;
    line-height: 34px;
    padding-top: 6px;
    background: #f2f2f2;
}
.popup-result {
    box-sizing: border-box;
    line-height: 24px;
    margin: 25px auto;
    padding: 15px 10px 10px;
    border: 1px solid #ccc;
    position: relative;
}
.popup-result .title {
    position: absolute;
    top: -28px;
    left: 50%;
    width: 140px;
    font-size: 14px;
    margin-left: -70px;
    text-align: center;
    line-height: 30px;
    background: #fff;
}
.popup-result table {
    text-align: center;
    width: 100%;
    margin: 0 auto;
}
.popup-result table td:not(.result) {
    width: 3.5rem;
    min-width: 3.5rem;
    max-width: 3.5rem;
}
.popup-result table span {
    display: block;
    width: 100%;
    font-family: arial;
    line-height: 30px;
    height: 30px;
    white-space: nowrap;
    overflow: hidden;
    border: 1px solid #e8e8e8;
}
.popup-result-scroll {
    font-size: 12px;
    line-height: 24px;
    height: 10em;
    overflow-y: auto;
}
</style>
