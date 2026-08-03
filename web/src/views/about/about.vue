<script lang="ts" setup>
import { computed, onMounted, ref } from "vue";
import { Search } from "@element-plus/icons-vue";
import QtrDocsBack from "@/components/hrm/common/qtr-docs-back.vue";

interface HelpDocItem {
    title: string;
    file: string;
    category: string;
    date: string;
    updatedAt: string;
    pinned: boolean;
}

interface HelpDocIndex {
    generatedAt: string;
    docs: HelpDocItem[];
}

const DEFAULT_DOC_FILE = "home.md";
const LEGACY_DOCS: HelpDocItem[] = [
    {
        title: "首页",
        file: "home.md",
        category: "首页与入门",
        date: "",
        updatedAt: "",
        pinned: true,
    },
    {
        title: "简介",
        file: "use_guide.md",
        category: "首页与入门",
        date: "",
        updatedAt: "",
        pinned: true,
    },
];

const markdownSource = ref("");
const docs = ref<HelpDocItem[]>([]);
const activeFile = ref(DEFAULT_DOC_FILE);
const searchKeyword = ref("");
const loading = ref(false);
const loadError = ref("");
const indexGeneratedAt = ref("");

function isMatchedKeyword(doc: HelpDocItem, keyword: string) {
    if (!keyword) {
        return true;
    }
    return `${doc.title} ${doc.file} ${doc.category}`.toLowerCase().includes(keyword);
}

const pinnedDocs = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase();
    return docs.value.filter((doc) => doc.pinned && isMatchedKeyword(doc, keyword));
});
const filteredDocs = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase();
    return docs.value.filter((doc) => !doc.pinned && isMatchedKeyword(doc, keyword));
});
const docsByCategory = computed(() => {
    return filteredDocs.value.reduce<Record<string, HelpDocItem[]>>((grouped, doc) => {
        if (!grouped[doc.category]) {
            grouped[doc.category] = [];
        }
        grouped[doc.category].push(doc);
        return grouped;
    }, {});
});
const categoryNames = computed(() => Object.keys(docsByCategory.value));
const currentDoc = computed(() => docs.value.find((doc) => doc.file === activeFile.value));

/**
 * 从构建期生成的索引中读取文档列表。
 * 浏览器不能直接枚举 public/docs 目录，所以由 Vite 插件在启动和构建时生成 docs-index.json。
 */
async function loadDocsIndex() {
    try {
        const response = await fetch("docs/docs-index.json", { cache: "no-cache" });
        if (!response.ok) {
            throw new Error(`索引请求失败：${response.status}`);
        }
        const data = (await response.json()) as HelpDocIndex;
        docs.value = data.docs?.length ? data.docs : LEGACY_DOCS;
        indexGeneratedAt.value = data.generatedAt || "";
    } catch (error) {
        console.error("加载帮助文档索引失败", error);
        docs.value = LEGACY_DOCS;
        loadError.value = "帮助文档索引加载失败，已回退到基础文档。";
    }
}

/**
 * 加载选中的 Markdown 文档内容。
 * 这里只读取 public/docs 下的相对路径，避免外部地址或上级目录被拼进 fetch。
 */
async function loadSource(fileName: string) {
    if (!fileName || fileName.includes("..")) {
        markdownSource.value = "文档路径不合法。";
        return;
    }

    activeFile.value = fileName;
    loading.value = true;
    loadError.value = "";
    try {
        const response = await fetch(`docs/${fileName}`, { cache: "no-cache" });
        if (response.ok) {
            markdownSource.value = await response.text();
        } else {
            loadError.value = `文档加载失败：${fileName}`;
            markdownSource.value = `# 文档加载失败\n\n未找到文档：${fileName}`;
        }
    } catch (error) {
        console.error("加载帮助文档失败", error);
        loadError.value = `文档加载异常：${fileName}`;
        markdownSource.value = "# 文档加载异常\n\n请检查文档文件是否存在。";
    } finally {
        loading.value = false;
    }
}

/**
 * 初始化帮助中心。
 * 优先打开首页；如果索引里没有首页，则打开第一篇可用文档。
 */
async function initDocs() {
    await loadDocsIndex();
    const defaultDoc = docs.value.find((doc) => doc.file === DEFAULT_DOC_FILE) || docs.value[0];
    if (defaultDoc) {
        await loadSource(defaultDoc.file);
    }
}

onMounted(() => {
    initDocs();
});
</script>

<template>
    <div class="help-page">
        <aside class="help-sidebar">
            <div class="help-sidebar__header">
                <div class="help-sidebar__title">帮助文档</div>
                <div class="help-sidebar__meta">自动收录 public/docs，按用户说明与更新记录分组</div>
            </div>
            <el-input
                v-model="searchKeyword"
                :prefix-icon="Search"
                clearable
                placeholder="搜索标题、文件名、分类"
                class="help-search"
            />
            <el-alert
                v-if="loadError"
                :title="loadError"
                type="warning"
                show-icon
                :closable="false"
                class="help-alert"
            />
            <el-scrollbar class="help-menu-scroll">
                <el-menu class="help-menu" :default-active="activeFile">
                    <el-sub-menu v-if="pinnedDocs.length" index="pinned">
                        <template #title>
                            <span>常用入口</span>
                        </template>
                        <el-menu-item
                            v-for="doc in pinnedDocs"
                            :key="`pinned-${doc.file}`"
                            :index="doc.file"
                            @click="loadSource(doc.file)"
                        >
                            <span class="help-menu__text">{{ doc.title }}</span>
                        </el-menu-item>
                    </el-sub-menu>
                    <el-sub-menu
                        v-for="category in categoryNames"
                        :key="category"
                        :index="category"
                    >
                        <template #title>
                            <span>{{ category }}</span>
                        </template>
                        <el-menu-item
                            v-for="doc in docsByCategory[category]"
                            :key="doc.file"
                            :index="doc.file"
                            @click="loadSource(doc.file)"
                        >
                            <span class="help-menu__text">{{ doc.title }}</span>
                            <span v-if="doc.date" class="help-menu__date">{{ doc.date }}</span>
                        </el-menu-item>
                    </el-sub-menu>
                </el-menu>
                <el-empty
                    v-if="!filteredDocs.length"
                    description="没有匹配的文档"
                    :image-size="80"
                />
            </el-scrollbar>
        </aside>
        <main class="help-content">
            <div class="help-toolbar">
                <div>
                    <div class="help-toolbar__title">
                        {{ currentDoc?.title || "帮助文档" }}
                    </div>
                    <div class="help-toolbar__desc">
                        <span v-if="currentDoc">{{ currentDoc.file }}</span>
                        <span v-if="indexGeneratedAt">索引生成：{{ indexGeneratedAt }}</span>
                    </div>
                </div>
            </div>
            <el-scrollbar class="help-content__scroll" v-loading="loading">
                <section class="help-markdown">
                    <QtrDocsBack v-model:markdown-source="markdownSource" />
                </section>
            </el-scrollbar>
        </main>
    </div>
</template>

<style scoped lang="scss">
.help-page {
    display: flex;
    height: 100vh;
    min-width: 0;
    background: #f5f7fa;
}

.help-sidebar {
    display: flex;
    flex-direction: column;
    width: 300px;
    min-width: 260px;
    border-right: 1px solid #dcdfe6;
    background: #ffffff;
}

.help-sidebar__header {
    padding: 16px 16px 8px;
}

.help-sidebar__title {
    font-size: 18px;
    font-weight: 700;
    color: #1f2d3d;
}

.help-sidebar__meta {
    margin-top: 4px;
    font-size: 12px;
    color: #909399;
}

.help-search {
    padding: 8px 12px 12px;
}

.help-alert {
    margin: 0 12px 12px;
    width: auto;
}

.help-menu-scroll {
    flex: 1;
}

.help-menu {
    border-right: 0;
}

.help-menu__text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.help-menu__date {
    margin-left: auto;
    padding-left: 8px;
    font-size: 12px;
    color: #909399;
}

.help-content {
    display: flex;
    flex: 1;
    min-width: 0;
    flex-direction: column;
}

.help-toolbar {
    display: flex;
    min-height: 64px;
    padding: 12px 24px;
    align-items: center;
    border-bottom: 1px solid #dcdfe6;
    background: #ffffff;
}

.help-toolbar__title {
    font-size: 18px;
    font-weight: 700;
    color: #1f2d3d;
}

.help-toolbar__desc {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 4px;
    font-size: 12px;
    color: #909399;
}

.help-content__scroll {
    flex: 1;
}

.help-markdown {
    max-width: 1180px;
    margin: 0 auto;
    padding: 24px 32px 48px;
    background: #ffffff;
    min-height: calc(100vh - 64px);
}
</style>
