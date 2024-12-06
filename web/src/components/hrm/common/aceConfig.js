// ace配置，使用动态加载来避免第一次加载开销
import ace from "ace-builds";

// 导入不同的主题模块，并设置对应 URL
import themeGithubUrl from "ace-builds/src-noconflict/theme-github?url";
ace.config.setModuleUrl("ace/theme/github", themeGithubUrl);

import themeGithubDark from "ace-builds/src-noconflict/theme-github_dark?url";
ace.config.setModuleUrl("ace/theme/github_dark", themeGithubDark);

import themeChromeUrl from "ace-builds/src-noconflict/theme-chrome?url";
ace.config.setModuleUrl("ace/theme/chrome", themeChromeUrl);

import themeMonokaiUrl from "ace-builds/src-noconflict/theme-monokai?url";
ace.config.setModuleUrl("ace/theme/monokai", themeMonokaiUrl);

import themeEclipse from "ace-builds/src-noconflict/theme-eclipse?url";
ace.config.setModuleUrl("ace/theme/eclipse", themeEclipse);

// 导入不同语言的语法模式模块，并设置对应 URL (所有支持的主题和模式：node_modules/ace-builds/src-noconflict)
import modeTextUrl from "ace-builds/src-noconflict/mode-text?url";
ace.config.setModuleUrl("ace/mode/text", modeTextUrl);

import modeJsonUrl from "ace-builds/src-noconflict/mode-json?url";
ace.config.setModuleUrl("ace/mode/json", modeJsonUrl);

import modeJavascriptUrl from "ace-builds/src-noconflict/mode-javascript?url";
ace.config.setModuleUrl("ace/mode/javascript", modeJavascriptUrl);

import modeHtmlUrl from "ace-builds/src-noconflict/mode-html?url";
ace.config.setModuleUrl("ace/mode/html", modeHtmlUrl);

import modePythonUrl from "ace-builds/src-noconflict/mode-python?url";
ace.config.setModuleUrl("ace/mode/python", modePythonUrl);

import modeYamlUrl from "ace-builds/src-noconflict/mode-yaml?url";
ace.config.setModuleUrl("ace/mode/yaml", modeYamlUrl);

// 用于完成语法检查、代码提示、自动补全等代码编辑功能，必须注册模块 ace/mode/lang _ worker，并设置选项 useWorker: true
import workerBaseUrl from "ace-builds/src-noconflict/worker-base?url";
ace.config.setModuleUrl("ace/mode/base", workerBaseUrl);

import workerJsonUrl from "ace-builds/src-noconflict/worker-json?url"; // for vite
ace.config.setModuleUrl("ace/mode/json_worker", workerJsonUrl);

import workerJavascriptUrl from "ace-builds/src-noconflict/worker-javascript?url";
ace.config.setModuleUrl("ace/mode/javascript_worker", workerJavascriptUrl);

import workerHtmlUrl from "ace-builds/src-noconflict/worker-html?url";
ace.config.setModuleUrl("ace/mode/html_worker", workerHtmlUrl);

// 导入不同语言的代码片段，提供代码自动补全和代码块功能
import snippetsJsonUrl from "ace-builds/src-noconflict/snippets/json?url";
ace.config.setModuleUrl("ace/snippets/json", snippetsJsonUrl);

import snippetsJsUrl from "ace-builds/src-noconflict/snippets/javascript?url";
ace.config.setModuleUrl("ace/snippets/javascript", snippetsJsUrl);

import snippetsHtmlUrl from "ace-builds/src-noconflict/snippets/html?url";
ace.config.setModuleUrl("ace/snippets/html", snippetsHtmlUrl);

import snippetsPyhontUrl from "ace-builds/src-noconflict/snippets/python?url";
ace.config.setModuleUrl("ace/snippets/python", snippetsPyhontUrl);

// 启用自动补全等高级编辑支持，
import extSearchboxUrl from "ace-builds/src-noconflict/ext-searchbox?url";
ace.config.setModuleUrl("ace/ext/searchbox", extSearchboxUrl);

//https://plnkr.co/edit/6MVntVmXYUbjR0DI82Cr?p=preview&preview
// const customCompleter = {
//   getCompletions: function (editor, session, pos, prefix, callback) {
//     // 自定义候选项
//     const completions = [
//       { caption: 'console.log', value: 'console.log()', meta: 'JavaScript', snippet: "console.log('content') \n\ 这是什么啊", completerId: "88888" },
//       { caption: 'function', value: 'function () {}', meta: 'Snippet' },
//       { caption: 'var', value: 'var ', meta: 'Keyword' },
//       { caption: 'test', value: 'test123 ', meta: 'Keyword' },
//     ];
//     callback(null, completions); // 传递补全项
//   },
// };
//
// const apiCompleter = {
//   getCompletions: async function (editor, session, pos, prefix, callback) {
//       console.log(prefix)
//     if (prefix.length === 0) return;
//     try {
//       const response = await fetch(`/api/completions?q=${prefix}`);
//       const suggestions = await response.json();
//       const completions = suggestions.map((item) => ({
//         caption: item.name,
//         value: item.value,
//         meta: item.type,
//       }));
//       callback(null, completions);
//     } catch (err) {
//       console.error('Error fetching completions:', err);
//       callback(null, []);
//     }
//   },
// };

// 启用自动补全等高级编辑支持
import "ace-builds/src-noconflict/ext-language_tools";
const languageTool = ace.require("ace/ext/language_tools");
// languageTool.setCompleters([customCompleter]);
// languageTool.addCompleter(apiCompleter);
