import fs from 'fs'
import path from 'path'

const DOCS_DIR = path.resolve(process.cwd(), 'public/docs')

const PINNED_DOCS = [
    'home.md',
    'use_guide.md',
    'case_config.md',
    'run.md',
    'configs.md',
    'hooks.md',
    'assert.md',
    'about_jobs.md',
    'about_forward.md',
    'web_case_use.md',
    'ticket-sync-automation.md',
    'update_history.md',
    'develop.md'
]

const CATEGORY_RULES = [
    { category: '首页与入门', keywords: ['home', 'use_guide', 'develop', 'server_startup'] },
    { category: '接口测试基础', keywords: ['case_config', 'run', 'configs', 'hooks', 'assert', 'web_case_use', 'about_jobs', 'about_forward'] },
    { category: '工单同步与多维表格', keywords: ['sync', 'bitable', 'pull', 'external', '多维', '同步', '拉取'] },
    { category: '工单日志与分析', keywords: ['log', '日志', 'analysis', '分析'] },
    { category: 'AI 与智能配置', keywords: ['ai', 'provider', 'prompt', 'translate', 'classification', 'classify', '智能', '分类', '翻译'] },
    { category: '通知提醒与消息', keywords: ['notify', 'reminder', 'message', 'mention', 'group', '通知', '提醒', '消息'] },
    { category: '业务说明', keywords: ['ticket', 'workflow', 'status', 'topic', 'statistics', 'module', 'store', '工单', '流程', '统计'] },
    { category: '配置说明', keywords: ['config', 'apikey', 'setup', 'env', '配置'] },
    { category: '变更记录', keywords: ['update_history'] }
]

function readMarkdownFiles(dir, baseDir = dir) {
    if (!fs.existsSync(dir)) {
        return []
    }

    return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
        const fullPath = path.join(dir, entry.name)
        if (entry.isDirectory()) {
            return readMarkdownFiles(fullPath, baseDir)
        }
        if (!entry.isFile() || !entry.name.endsWith('.md')) {
            return []
        }
        return path.relative(baseDir, fullPath).replace(/\\/g, '/')
    })
}

function readDocTitle(content, filePath) {
    const frontmatterTitle = content.match(/^---[\s\S]*?\ntitle:\s*["']?(.+?)["']?\s*\n[\s\S]*?---/)
    if (frontmatterTitle?.[1]) {
        return frontmatterTitle[1].trim()
    }

    const headingTitle = content.match(/^#\s+(.+)$/m)
    if (headingTitle?.[1]) {
        return headingTitle[1].trim()
    }

    return path.basename(filePath, '.md').replace(/[-_]/g, ' ')
}

function pickCategory(filePath, title) {
    const searchText = `${filePath} ${title}`.toLowerCase()
    const matchedRule = CATEGORY_RULES.find((rule) => rule.keywords.some((keyword) => searchText.includes(keyword.toLowerCase())))
    return matchedRule?.category || '其他文档'
}

function getDocDate(filePath, stat) {
    const fileDate = path.basename(filePath).match(/^(\d{4})-?(\d{2})-?(\d{2})/)
    if (fileDate) {
        return `${fileDate[1]}-${fileDate[2]}-${fileDate[3]}`
    }
    return stat.mtime.toISOString().slice(0, 10)
}

function buildDocsIndex() {
    const docs = readMarkdownFiles(DOCS_DIR)
        .map((filePath) => {
            const fullPath = path.join(DOCS_DIR, filePath)
            const content = fs.readFileSync(fullPath, 'utf-8')
            const stat = fs.statSync(fullPath)
            const title = readDocTitle(content, filePath)
            return {
                title,
                file: filePath,
                category: pickCategory(filePath, title),
                date: getDocDate(filePath, stat),
                updatedAt: stat.mtime.toISOString(),
                pinned: PINNED_DOCS.includes(filePath)
            }
        })
        .sort((left, right) => {
            if (left.pinned !== right.pinned) {
                return left.pinned ? -1 : 1
            }
            return right.updatedAt.localeCompare(left.updatedAt)
        })

    return { generatedAt: new Date().toISOString(), docs }
}

export default function createDocsIndex() {
    return {
        name: 'vite-plugin-docs-index',
        generateBundle() {
            this.emitFile({
                type: 'asset',
                fileName: 'docs/docs-index.json',
                source: `${JSON.stringify(buildDocsIndex(), null, 2)}\n`
            })
        },
        configureServer(server) {
            server.watcher.add(DOCS_DIR)
            server.middlewares.use('/docs/docs-index.json', (_request, response) => {
                response.setHeader('Content-Type', 'application/json; charset=utf-8')
                response.end(`${JSON.stringify(buildDocsIndex(), null, 2)}\n`)
            })
        }
    }
}
