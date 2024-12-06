<script setup>
import hljs from 'highlight.js';
import {useTemplateRef} from 'vue';
import markdownit from 'markdown-it'
import Hooks from "../../../docs/hooks.md?raw"

const dialogShow = ref(false);
const markdownContainer = ref();
const markdownContainerRef = useTemplateRef("markdownContainer");
const markdownContent = ref("");


function renderMarkdownByMarkdownIt() {
  const md = markdownit({
    // html: true,
    // linkify: true,
    // typographer: true,
    // langPrefix: 'language-',
    highlight: function (str, lang) {
      if (lang && hljs.getLanguage(lang)) {
        try {
          return '<pre><code class="hljs">' +
               hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
               '</code></pre>';
        } catch (__) {
        }
      }

      return '<pre><code class="hljs">' + md.utils.escapeHtml(str) + '</code></pre>';
    }
  });


// 自定义规则，使链接在新页签中打开
  md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
    debugger
    const aIndex = tokens[idx].attrIndex('target');

    if (aIndex !== -1) {
      // 如果已经有 target 属性，则不做处理
      return self.renderToken(tokens, idx, options);
    }

    // 添加 target="_blank" 属性
    tokens[idx].attrPush(['target', '_blank']);
    tokens[idx].attrPush(['rel', 'noopener noreferrer']);

    // 渲染标签
    return self.renderToken(tokens, idx, options);

  };

  // let content = md.render(Hooks);
  // markdownContainer.innerHTML = content; // 清空之前的内容
  // markdownContainer.appendChild(app.el); // 挂载编译后的组件

  markdownContent.value = md.render(Hooks);
}

function handleLinkClick(event) {
  const target = event.target.closest('a');

  if (target && target.classList.contains('internal-link')) {
    event.preventDefault();
    const href = target.getAttribute('href');
    // 使用 Vue Router 进行导航
    $toRef.router.push(href);
  }
}


onMounted(() => {
  renderMarkdownByMarkdownIt();
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
      <div ref="markdownContainer" v-html="markdownContent"></div>
      <!--      <div v-html="markdownContent"></div>-->
    </el-dialog>
  </div>


</template>

<style scoped lang="scss">

</style>