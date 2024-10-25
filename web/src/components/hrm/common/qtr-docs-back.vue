<script setup>
import {marked} from 'marked';
import hljs from 'highlight.js';

import MarkdownItHighlightjs from 'markdown-it-highlightjs'
import MarkdownItContainer from 'markdown-it-container'
import MarkdownItDeflist from 'markdown-it-deflist'
import MarkdownItIns from 'markdown-it-ins'

import MarkdownItAbbr from 'markdown-it-abbr'
import MarkdownItAnchor from 'markdown-it-anchor'
import MarkdownItFootnote from 'markdown-it-footnote'
import MarkdownItSub from 'markdown-it-sub'
import MarkdownItSup from 'markdown-it-sup'
import MarkdownItTasklists from 'markdown-it-task-lists'
import MarkdownItTOCDR from 'markdown-it-toc-done-right'

import 'highlight.js/styles/default.css'


import {useTemplateRef, compile, render} from 'vue';
import markdownit from 'markdown-it'
import Hooks from "../../../docs/hooks.md?raw"
import caseConfig from "../../../docs/case_config.md?raw"
import {useRouter} from "vue-router";


const dialogShow = ref(false);
const markdownContainer = ref();
const markdownContainerRef = useTemplateRef("markdownContainer");
const markdownContent = ref("");

const router = useRouter();


const md = markdownit({
  html: true,
  breaks: true,
  linkify: true,
  typographer: true,
  langPrefix: 'language-',
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre><code class="hljs">' +
            hljs.highlight(str, {language: lang, ignoreIllegals: true}).value +
            '</code></pre>';
      } catch (__) {
      }
    }

    return '<pre><code class="hljs">' + md.utils.escapeHtml(str) + '</code></pre>';
  }
})
    .use(MarkdownItHighlightjs)
    .use(MarkdownItContainer)
    .use(MarkdownItDeflist)
    .use(MarkdownItIns)
    .use(MarkdownItAbbr)
    .use(MarkdownItAnchor)
    .use(MarkdownItFootnote)
    .use(MarkdownItSub).use(MarkdownItSup).use(MarkdownItTasklists).use(MarkdownItTOCDR)


// 自定义规则，使链接在新页签中打开
md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  const aIndex = tokens[idx].attrIndex('target');

  if (aIndex !== -1) {
    // 如果已经有 target 属性，则不做处理
    return self.renderToken(tokens, idx, options);
  }

  // 添加 target="_blank" 属性
  tokens[idx].attrPush(['target', '_blank']);
  tokens[idx].attrPush(['rel', 'noopener noreferrer']);
  tokens[idx].attrPush(['class', 'internal-link']);

  // 渲染标签
  return self.renderToken(tokens, idx, options);

};

// let content = md.render(Hooks);
// markdownContainer.innerHTML = content; // 清空之前的内容
// markdownContainer.appendChild(app.el); // 挂载编译后的组件


markdownContent.value = md.render(Hooks);


function handleLinkClick(event) {
  const target = event.target.closest('a');

  if (target && target.classList.contains('internal-link')) {
    debugger
    event.preventDefault();
    const href = target.getAttribute('href');
    if (href && href.startsWith('#')) {
      window.location.hash = href.replace('#', '');
      // 使用 Vue Router 进行导航
      router.push(href);
    }else {
      const baseUrl = window.location.origin; // 获取当前网站根URL
      const fullUrl = baseUrl + href; // 拼接完整的URL
      window.open(fullUrl, '_blank'); // 在新标签页中打开
    }
  }
}

watch(markdownContainerRef, () => {
  markdownContainerRef.value && markdownContainerRef.value.addEventListener('click', handleLinkClick);
})

onMounted(() => {
  markdownContainerRef.value && markdownContainerRef.value.addEventListener('click', handleLinkClick);
});

onBeforeUnmount(() => {
  markdownContainerRef.value && markdownContainerRef.value.removeEventListener('click', handleLinkClick);
});


// // 创建自定义渲染器
// const renderer = new marked.Renderer();


// // 重写 link 渲染器
// renderer.link = function (oldHref, title, text) {
//   // 如果链接是内部链接，转换为 router-link
//   debugger
//   let href = oldHref.href;
//   if (href && href.startsWith('#')) {
//     return `<router-link to="${href.replace('#', '')}">${oldHref.text}</router-link>`;
//   } else {
//     // 否则返回普通的 a 标签
//     return `<a href="${href}" target="_blank">${oldHref.text}</a>`;
//   }
// };
//
// // 使用 marked 解析 Markdown 为 HTML
// const htmlContent = marked(Hooks, {renderer});
//
// // 将 HTML 字符串编译为 Vue 组件
// const compiledTemplate = compile(`<div>${htmlContent}</div>`);
//
// // 将编译后的组件渲染到页面上
// const app = compiledTemplate();
// markdownContainer.innerHTML = ''; // 清空之前的内容
// markdownContainer.appendChild(app.el); // 挂载编译后的组件

// const markdownContent = ref(marked(Hooks, {renderer}));

function showDocs() {
  dialogShow.value = true;
}

</script>

<template>
  <div>
    <svg-icon icon-class="question" @click="showDocs"/>
    <el-dialog v-model="dialogShow">
      <div ref="markdownContainer" v-html="markdownContent" class="docsContainer"></div>
      <!--      <div v-html="markdownContent"></div>-->
    </el-dialog>
  </div>


</template>

<style scoped lang="scss">


.docsContainer {
  :deep(table) {
    border-collapse: collapse;
    width: 100%;

    th {
      border: 1px solid #ddd;
      padding: 8px;
      text-align: left;
    }

    td {
      border: 1px solid #ddd;
      padding-left: 8px;
      text-align: left;
      margin: 1px;
    }

    tr {
      line-height: 25px;
    }

    th {
      background-color: #f2f2f2;
    }

  }


  //width: 1400px;
  :deep(h1) {
    font-size: 24px;
    line-height: 40px;
    font-weight: 800;
  }

  :deep(h2) {
    font-size: 22px;
    line-height: 35px;
    font-weight: 700;
  }

  :deep(h3) {
    font-size: 20px;
    line-height: 30px;
    font-weight: 600;
  }

  :deep(h4) {
    font-size: 18px;
    line-height: 25px;
    font-weight: 500;
  }

  :deep(h5) {
    font-size: 16px;
    line-height: 20px;
    font-weight: 400;
  }

  :deep(h6) {
    font-size: 14px;
    line-height: 18px;
    font-weight: 300;
  }

  :deep(img) {
    width: 500px;
  }

  :deep(a) {
    color: #335fee;
    line-height: 20px;
  }

  :deep(p) {
    line-height: 20px;
  }

  :deep(li) {
    line-height: 20px;
  }

  :deep(blockquote) {
    margin-left: 0;
    margin-right: 0;
    padding: 5px;
    background-color: #F3F3F3;
    //border-left-width: 2px;
    //border-left-color: #1c84c6;
    border-radius: 10px;

    border-left: 2px solid darkseagreen; /* 左侧边框作为竖线 */
    padding-left: 10px; /* 确保文本与竖线之间有间距 */
  }

  :deep(pre) {
  }

  :deep(code.hljs) {
    line-height: 1.2;
    border-radius: 10px;
  }
}
</style>