

export function randomString(length) {
    var text = "";
    var possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    for (var i = 0; i < length; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}

export function randomNumber(length) {
    return Math.floor(Math.random() * 10**length);
}


export class Json {

    /*
    * 美化json，返回字符串，输入json字符串或者js对象，输出格式化后的json字符串，一般调用这个方法就行了
    * */
    static beautifulJson(jsonStr) {
        let jsonObj = jsonStr;
        if (typeof jsonStr == "string") {
            let jsonObjTmp = "";
            try {
                // let tttt = jsonStr.replace(/(['"])?([a-zA-Z0-9_]+)(['"])?:/g, '"$2": ');
                let tttt = jsonStr.replace(/([{,]\s*)([0-9]+)(\s*:)/g, '$1"$2"$3');
                jsonObjTmp = JSON5.parse(tttt);
                // jsonObjTmp = jsonlint.parse(jsonStr);
                // jsonObjTmp = JSON.parse(jsonStr);
            } catch (e1) {
                let beautifulStr = this.beautifulJsonAuto(jsonStr);
                // let beautifulStr = this.parseJsonWithRegex(jsonStr);
                try {
                    jsonObjTmp = JSON.parse(beautifulStr);
                } catch (e2) {
                    return jsonObj;
                }
            }
            jsonObj = jsonObjTmp
        }
        return JSON.stringify(jsonObj, null, 4);


    }

    /*
    * json压缩
    * */
    static compressJson(jsonStr) {
        if (typeof jsonStr == "string") {
            return JSON.stringify(JSON.parse(jsonStr));
        } else {
            return JSON.stringify(jsonStr);
        }
    }

    /*
    * 压缩并转义
    * */
    static compressAndEscape(json) {
        json = this.compressJson(json);
        return json.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    }

    /*
    * 删除转义符
    * */
    static removeEscape(jsonStr) {
        // return jsonStr.replace(/\\(.)/g, '$1');
        return jsonStr.replace(new RegExp("\\\\\"", "gm"), "\"");
    }

    /*
     * 格式化json
     * 通过统计{}[]，自动识别多个json混在一起的情况。
     * https://blog.csdn.net/yiluochenwu/article/details/119346326
     * 你建议直接使用
     */
    static beautifulJsonAuto(input) {
        var s = input.trim(); // 忽略前后的空白
        var res = '';

        var eCharMap = {
            '[': ']',
            '{': '}'
        }

        // b是begin, e是end, cnt是count
        var bChar = '', eChar = '', cnt = 0;

        // 压缩还是美化，这里只是压缩。可以通过统计换行来决定是压缩还是美化。
        var isStrip = false;

        var bIndex = 0, eIndex = -1;
        for (var i = 0; i < input.length; i++) {
            var ch = input[i];
            if (eCharMap[ch]) {
                if (cnt == 0 && i != 0) { // 开始新一轮匹配之前
                    // 不是json的内容
                    eIndex = i;
                    var t = s.substring(bIndex, eIndex);
                    res = res + "\n" + t;
                }

                if (cnt == 0) {
                    bChar = ch, eChar = eCharMap[ch], cnt = 1, bIndex = i;
                    continue;
                } else if ((ch == bChar)) {
                    cnt = cnt + 1;
                    continue;
                }

            } else if (ch == eChar) {
                cnt = cnt - 1; // 匹配到后就减少
                if (cnt == 0) { // 完成了一次完整的匹配
                    eIndex = i + 1;
                    var t = s.substring(bIndex, eIndex);
                    t = this.beautify(t, isStrip);
                    res = res + '\n' + t;
                    bIndex = i + 1;
                    continue;
                }
            }
        }
        // 如果还没有处理完，直接加上
        if (cnt != 0) {
            res = res + '\n' + s.substring(bIndex, input.length);
        }
        return res;
    }


    /*
     * isStrip true 为压缩
     * 不建议直接使用
     */
    static beautify(s, isStrip) {
        // 处理不是合法的json
        try {
            eval('obj=' + s);
        } catch (e) {
            return s;
        }

        // 如果包含换行，则压缩
        if (isStrip) {
            return JSON.stringify(obj);
        }

        // 否则美化
        return JSON.stringify(obj, null, 2);
    }


    /*
    * json字符串对象化，可以是json字符串也可以是json对象
    * @param {string|obj} jsonString
    * @returns {obj}
    * */
    static parse(jsonString) {
        if (typeof jsonString === 'string') {
            return JSON.parse(this.beautifulJson(jsonString));
        }
        return jsonString;
    }

}

/*
* 解压文本内容
* */
export function decompressText(compressedText) {
    let strData = atob(compressedText);
    let charData = strData.split('').map(function (x) {return x.charCodeAt(0);});
    let binData = new Uint8Array(charData);
    let data = pako.inflate(binData, {"to": "string"});
    return data;
}


/*
* 压缩数据glib
* */
export function zipData(data) {
    if (!data) return data
    // 判断数据是否需要转为JSON
    const dataJson = typeof data !== 'string' && typeof data !== 'number' ? JSON.stringify(data) : data

    // 使用Base64.encode处理字符编码，兼容中文
    // const str = Base64.encode(dataJson)
    let binaryString = pako.deflate(dataJson);
    let arr = Array.from(binaryString);
    let s = "";
    arr.forEach((item, index) => {
    s += String.fromCharCode(item)
    })
    return btoa(s)
}