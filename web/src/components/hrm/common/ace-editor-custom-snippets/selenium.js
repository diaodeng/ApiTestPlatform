

ace.define("ace/snippets/customSelenium.snippets",["require","exports","module"], function(require, exports, module){module.exports = "snippet #!\n" +
    "\t#!/usr/bin/env python\n" +
    "snippet click\n" +
    "\tclick(${1:local}, ${1:timeout}) \n" +
    "snippet goto\n" +
    "\tgoto(${1:url})\n" +
    "# Module Docstring\n" +
    "snippet open\n" +
    "\topen(${1:url})\n" +
    "\t'''\n" +
    "\tFile: ${1:FILENAME:file_name}\n" +
    "\tAuthor: ${2:author}\n" +
    "\tDescription: ${3}\n" +
    "\t'''\n" +
    "\n";

});

ace.define("ace/snippets/customSelenium",["require","exports","module","ace/snippets/customSelenium.snippets"], function(require, exports, module){"use strict";
exports.snippetText = require("./customSelenium.snippets");
exports.scope = "customSelenium";

});                (function() {
                    ace.require(["ace/snippets/customSelenium"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();