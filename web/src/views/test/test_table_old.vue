<template>
  <div class="rf-editor-container">
    <!-- 操作控件区域 -->
    <div class="control-bar">
      <el-button type="primary" @click="addRow">添加行</el-button>
      <el-button type="primary" @click="addColumn">添加列</el-button>
      <el-button @click="resetTable">重置表格</el-button>

      <!-- 列管理下拉菜单 -->
      <el-dropdown @command="handleColumnCommand">
        <el-button type="primary">
          列管理<el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="(col, colIndex) in columnHeaders"
              :key="colIndex"
              :command="{ type: 'delete', index: colIndex }"
            >
              <div class="column-dropdown-item">
                <span>删除列: {{ col }}</span>
                <el-tag v-if="colIndex === 0" size="small" type="info">主列</el-tag>
              </div>
            </el-dropdown-item>
            <el-dropdown-item divided command="deleteEmptyColumns">
              删除空列
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <div class="method-list">
        <span class="method-label">预定义方法：</span>
        <el-popover
          v-for="method in Object.keys(methodDefinitions)"
          :key="method"
          placement="top"
          :width="300"
          trigger="hover"
        >
          <template #reference>
            <el-tag
              class="method-tag"
              size="small"
            >
              {{ method }}
            </el-tag>
          </template>
          <div class="method-detail-popover">
            <h4>{{ method }}</h4>
            <p><strong>描述：</strong>{{ getMethodDefinition(method).description }}</p>
            <p><strong>参数数量：</strong>{{ getMethodDefinition(method).params === -1 ? '可变参数' : getMethodDefinition(method).params }}</p>
            <p v-if="getMethodDefinition(method).example">
              <strong>示例：</strong>{{ getMethodDefinition(method).example }}
            </p>
          </div>
        </el-popover>
      </div>
    </div>

    <!-- 主表格 -->
    <el-table
      :data="tableData"
      border
      stripe
      style="width: 100%"
      :row-class-name="tableRowClassName"
      :max-height="600"
    >
      <!-- 动态生成列 -->
      <el-table-column
        v-for="(col, colIndex) in columnHeaders"
        :key="colIndex"
        :prop="`cells[${colIndex}]`"
        :label="col"
        min-width="150"
      >
        <template #header>
          <div class="column-header">
            <span>{{ col }}</span>
            <el-button
              v-if="columnHeaders.length > 1"
              type="default"
              size="small"
              @click="removeColumn(colIndex)"
              icon="Close"
              class="delete-column-btn"
              title="删除此列"
            />
          </div>
        </template>

        <template #default="{ row, $index: rowIndex }">
          <!-- 智能下拉输入框 -->
          <el-autocomplete
            v-model="row.cells[colIndex]"
            :fetch-suggestions="(queryString, cb) => querySuggestions(queryString, cb, rowIndex, colIndex)"
            :trigger-on-focus="true"
            :placeholder="getPlaceholder(rowIndex, colIndex)"
            class="cell-autocomplete"
            :class="getCellClass(rowIndex, colIndex)"
            @select="handleSelectSuggestion(rowIndex, colIndex, $event)"
            @input="handleCellInput(rowIndex, colIndex)"
            @blur="validateRow(rowIndex)"
            :title="getCellTitle(rowIndex, colIndex)"
            :disabled="isCellDisabled(rowIndex, colIndex)"
            clearable
            :popper-class="getPopperClass(rowIndex, colIndex)"
          >
            <template #default="{ item }">
              <div class="suggestion-item">
                <!-- 变量项 -->
                <div v-if="item.type === 'variable'" class="suggestion-variable">
                  <div class="variable-image-container" v-if="item.image">
                    <el-image
                      :src="item.image.thumbnail || item.image.url"
                      :preview-src-list="[item.image.url]"
                      fit="cover"
                      lazy
                      class="variable-image-thumb"
                      :alt="item.description"
                    >
                      <template #error>
                        <div class="image-error">
                          <el-icon><Picture /></el-icon>
                        </div>
                      </template>
                    </el-image>
                  </div>
                  <div class="variable-icon" v-else>
                    <el-icon :size="16" :color="getVariableIconColor(item)">
                      <component :is="getVariableIcon(item)" />
                    </el-icon>
                  </div>
                  <div class="suggestion-content">
                    <div class="suggestion-main">
                      <strong>{{ item.name }}</strong>
                      <el-tag v-if="item.category" size="mini" :type="getCategoryTagType(item.category)">
                        {{ getCategoryName(item.category) }}
                      </el-tag>
                    </div>
                    <div class="suggestion-desc">{{ item.description }}</div>
                  </div>
                </div>

                <!-- 方法项 -->
                <div v-else class="suggestion-method">
                  <div class="suggestion-content">
                    <div class="suggestion-main">
                      <strong>{{ item.name }}</strong>
                      <span class="suggestion-params">
                        {{ item.params === -1 ? '可变参数' : `${item.params}个参数` }}
                      </span>
                    </div>
                    <div class="suggestion-desc">{{ truncateDescription(item.description) }}</div>
                  </div>
                </div>
              </div>
            </template>

            <!-- 输入框后缀图标 -->
            <template #suffix>
              <el-tooltip
                v-if="row.cells[colIndex]"
                :content="getCellTitle(rowIndex, colIndex)"
                placement="top"
                :show-after="300"
              >
                <el-icon><View /></el-icon>
              </el-tooltip>
            </template>
          </el-autocomplete>
        </template>
      </el-table-column>

      <!-- 额外列（超出表头部分） -->
      <el-table-column
        v-if="hasExtraColumns"
        label="额外参数"
        min-width="200"
      >
        <template #default="{ row, $index: rowIndex }">
          <div class="extra-cells">
            <el-tooltip
              v-for="(cell, extraIndex) in row.cells.slice(columnHeaders.length)"
              :key="extraIndex"
              :content="`参数值: ${cell || '(空)'}`"
              placement="top"
              :show-after="300"
            >
              <el-tag
                class="extra-cell-tag"
                :class="getExtraCellClass(rowIndex, extraIndex + columnHeaders.length)"
                :title="getCellTitle(rowIndex, extraIndex + columnHeaders.length)"
                size="small"
                disable-transitions
              >
                {{ truncateCellValue(cell) }}
              </el-tag>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>

      <!-- 操作列 -->
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ $index: rowIndex }">
          <el-button
            type="danger"
            size="small"
            @click="removeRow(rowIndex)"
            icon="Delete"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 代码预览 -->
    <div class="preview-section">
      <h3>Robot Framework 代码预览</h3>
      <el-alert
        v-if="invalidRowsCount > 0"
        :title="`有 ${invalidRowsCount} 行格式无效，请检查`"
        type="warning"
        show-icon
        :closable="false"
      />
      <pre class="code-preview">{{ formatAsRobotFramework }}</pre>
    </div>
  </div>
</template>

<script>
import { ref, computed, reactive, toRefs, onMounted } from 'vue'
import {
  ElTable,
  ElTableColumn,
  ElInput,
  ElAutocomplete,
  ElButton,
  ElTag,
  ElAlert,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElPopover,
  ElTooltip,
  ElImage,
  ElMessage
} from 'element-plus'
import {
  ArrowDown,
  View,
  Close,
  Delete,
  Picture,
  Picture as PictureIcon,
  Document as DocumentIcon,
  DataBoard,
  Collection,
  Warning
} from '@element-plus/icons-vue'

export default {
  name: 'RobotFrameworkEditor',
  components: {
    ElTable,
    ElTableColumn,
    ElInput,
    ElAutocomplete,
    ElButton,
    ElTag,
    ElAlert,
    ElDropdown,
    ElDropdownMenu,
    ElDropdownItem,
    ElPopover,
    ElTooltip,
    ElImage,
    ArrowDown,
    View,
    Close,
    Delete,
    Picture,
    PictureIcon,
    DocumentIcon,
    DataBoard,
    Collection,
    Warning
  },
  setup() {
    // 状态定义
    const state = reactive({
      // 表格数据
      tableData: [
        { cells: ['${result}', 'Log', 'Hello World'], isValid: true },
        { cells: ['Log To Console', 'Test message'], isValid: true },
        { cells: ['${value}', 'Set Variable', 'test_value'], isValid: true },
        { cells: ['Run Keyword If', '${condition}', 'Log', 'Condition is true'], isValid: true }
      ],
      // 列标题
      columnHeaders: ['单元格1', '单元格2', '单元格3', '单元格4'],
      // 预定义方法及其参数数量
      methodDefinitions: {
        'Log': {
          params: 1,
          description: '将指定消息记录到日志文件中，支持多种日志级别（INFO、WARN、DEBUG等）',
          example: 'Log    Hello World'
        },
        'Log To Console': {
          params: 1,
          description: '将消息输出到控制台，便于调试和实时监控',
          example: 'Log To Console    Test message'
        },
        'Set Variable': {
          params: 1,
          description: '创建一个新变量或修改现有变量的值，支持各种数据类型',
          example: '${result}    Set Variable    ${value}'
        },
        'Should Be Equal': {
          params: 2,
          description: '比较两个值是否相等，如果不相等则测试失败，支持自定义错误消息',
          example: 'Should Be Equal    ${var1}    ${var2}'
        },
        'Run Keyword If': {
          params: 3,
          description: '根据条件执行关键字，支持嵌套条件和多个分支',
          example: 'Run Keyword If    ${condition}    Log    Condition is true'
        },
        'Get Length': {
          params: 1,
          description: '获取列表、字典或字符串的长度，返回整数值',
          example: '${length}    Get Length    ${list}'
        },
        'Convert To String': {
          params: 1,
          description: '将任意类型的值转换为字符串表示，便于日志输出和比较',
          example: '${str}    Convert To String    123'
        },
        'Should Contain': {
          params: 2,
          description: '检查第一个参数是否包含第二个参数，支持列表、字符串等多种类型',
          example: 'Should Contain    ${list}    item'
        },
        'Create List': {
          params: -1,
          description: '创建一个新的列表，支持任意数量的参数，参数将成为列表元素',
          example: '${list}    Create List    a    b    c'
        },
        'Evaluate': {
          params: 1,
          description: '执行Python表达式并返回结果，支持导入模块和复杂计算',
          example: '${result}    Evaluate    1 + 2 * 3'
        }
      },
      // 变量定义数据
      variableDefinitions: []
    })

    // 计算属性
    const invalidRowsCount = computed(() => {
      return state.tableData.filter(row => !row.isValid).length
    })

    const hasExtraColumns = computed(() => {
      return state.tableData.some(row => row.cells.length > state.columnHeaders.length)
    })

    const formatAsRobotFramework = computed(() => {
      return state.tableData
        .map(row => {
          if (row.isValid) {
            return row.cells.join('    ')
          } else {
            return `# 无效行: ${row.cells.join('    ')}`
          }
        })
        .join('\n')
    })

    // 工具方法
    const truncateDescription = (desc) => {
      if (!desc) return ''
      return desc.length > 40 ? desc.substring(0, 40) + '...' : desc
    }

    const truncateCellValue = (value) => {
      if (!value) return '(空)'
      return value.length > 20 ? value.substring(0, 20) + '...' : value
    }

    // 获取变量图标
    const getVariableIcon = (variable) => {
      switch (variable.category) {
        case 'image': return PictureIcon
        case 'text': return DocumentIcon
        case 'data': return DataBoard
        default: return Collection
      }
    }

    // 获取变量图标颜色
    const getVariableIconColor = (variable) => {
      switch (variable.category) {
        case 'image': return '#67C23A'
        case 'text': return '#409EFF'
        case 'data': return '#E6A23C'
        default: return '#909399'
      }
    }

    // 获取分类标签类型
    const getCategoryTagType = (category) => {
      switch (category) {
        case 'image': return 'success'
        case 'text': return 'primary'
        case 'data': return 'warning'
        default: return 'info'
      }
    }

    // 获取分类名称
    const getCategoryName = (category) => {
      switch (category) {
        case 'image': return '图片'
        case 'text': return '文本'
        case 'data': return '数据'
        default: return '其他'
      }
    }

    // 判断是否为变量（如 ${result}）
    const isVariable = (value) => {
      if (!value) return false
      const trimmed = value.trim()
      // 检查是否以$开头或者是${...}格式
      return trimmed.startsWith('$') || /^\$\{[^{}]+\}$/.test(trimmed)
    }

    // 判断是否为预定义的方法
    const isMethod = (value) => {
      if (!value) return false
      return Object.keys(state.methodDefinitions).includes(value.trim())
    }

    // 获取方法定义
    const getMethodDefinition = (methodName) => {
      return state.methodDefinitions[methodName?.trim()] || { params: 0, description: '' }
    }

    // 获取方法描述
    const getMethodDescription = (methodName) => {
      const def = state.methodDefinitions[methodName]
      return def ? `${methodName}: ${def.description} (需要${def.params}个参数)` : ''
    }

    // 获取单元格的CSS类
    const getCellClass = (rowIndex, colIndex) => {
      const row = state.tableData[rowIndex]
      if (!row || colIndex >= row.cells.length) return ''

      const cellValue = row.cells[colIndex]?.trim() || ''

      // 第一列特殊处理
      if (colIndex === 0) {
        if (isVariable(cellValue)) {
          return 'cell-variable'
        } else if (isMethod(cellValue)) {
          return 'cell-method'
        }
      }

      // 第二列（当第一列是变量时，第二列可能是方法）
      if (colIndex === 1 && row.cells[0]) {
        const firstCell = row.cells[0]?.trim() || ''
        if (isVariable(firstCell) && isMethod(cellValue)) {
          return 'cell-method'
        }
      }

      // 参数单元格
      if (colIndex > 0) {
        return 'cell-param'
      }

      return ''
    }

    // 获取额外单元格的CSS类
    const getExtraCellClass = (rowIndex, colIndex) => {
      const row = state.tableData[rowIndex]
      if (!row || colIndex >= row.cells.length) return ''

      const cellValue = row.cells[colIndex]?.trim() || ''

      // 检查是否是参数单元格
      const firstCell = row.cells[0]?.trim() || ''
      if (isVariable(firstCell)) {
        // 第一列是变量，第二列是方法
        if (colIndex >= 2 && isMethod(row.cells[1]?.trim() || '')) {
          return 'cell-param-disabled'
        }
      } else if (isMethod(firstCell)) {
        // 第一列是方法
        if (colIndex >= 1) {
          return 'cell-param-disabled'
        }
      }

      return ''
    }

    // 获取单元格提示信息
    const getCellTitle = (rowIndex, colIndex) => {
      const row = state.tableData[rowIndex]
      if (!row || colIndex >= row.cells.length) return ''

      const cellValue = row.cells[colIndex]?.trim() || ''

      if (colIndex === 0) {
        if (isVariable(cellValue)) {
          return '返回值存储变量，例如: ${result}'
        } else if (isMethod(cellValue)) {
          const methodDef = getMethodDefinition(cellValue)
          return methodDef ? `${cellValue}: ${methodDef.description} (${methodDef.params}个参数)` : '方法名'
        }
        return '输入方法名或变量（以$开头）'
      }

      if (colIndex === 1) {
        const firstCell = row.cells[0]?.trim() || ''
        if (isVariable(firstCell)) {
          if (isMethod(cellValue)) {
            const methodDef = getMethodDefinition(cellValue)
            return methodDef ? `${cellValue}: ${methodDef.description} (${methodDef.params}个参数)` : '方法名'
          }
          return '此处应输入方法名'
        }
      }

      // 检查是否是参数单元格
      if (colIndex > 0) {
        const firstCell = row.cells[0]?.trim() || ''
        if (isVariable(firstCell)) {
          // 第一列是变量，第二列是方法
          if (colIndex >= 2 && isMethod(row.cells[1]?.trim() || '')) {
            return '参数值（可以是变量）'
          }
        } else if (isMethod(firstCell)) {
          // 第一列是方法
          if (colIndex >= 1) {
            return '参数值（可以是变量）'
          }
        }
      }

      // 额外列的提示
      if (colIndex >= state.columnHeaders.length) {
        return '额外参数（已禁用编辑）'
      }

      return '输入参数值'
    }

    // 获取占位符文本
    const getPlaceholder = (rowIndex, colIndex) => {
      if (colIndex === 0) {
        return '输入方法名或变量（以$开头）'
      }

      const row = state.tableData[rowIndex]
      if (!row) return '输入值'

      const firstCell = row.cells[0]?.trim() || ''

      if (colIndex === 1 && isVariable(firstCell)) {
        return '输入方法名'
      }

      return '输入参数值'
    }

    // 获取下拉框类名
    const getPopperClass = (rowIndex, colIndex) => {
      const row = state.tableData[rowIndex]
      if (!row) return ''

      const cellValue = row.cells[colIndex]?.trim() || ''

      // 如果是第一列且以$开头，或者不是第一列但需要显示变量列表
      if (colIndex === 0 && cellValue.startsWith('$')) {
        return 'variable-popper'
      }

      if (colIndex > 0) {
        const firstCell = row.cells[0]?.trim() || ''
        if (isVariable(firstCell)) {
          // 第一列是变量
          if (colIndex === 1) {
            return 'method-popper'
          } else {
            return 'variable-popper'
          }
        } else if (isMethod(firstCell)) {
          // 第一列是方法
          return 'variable-popper'
        }
      }

      return 'method-popper'
    }

    // 判断单元格是否禁用
    const isCellDisabled = (rowIndex, colIndex) => {
      const row = state.tableData[rowIndex]
      if (!row || !row.isValid) return false

      const firstCell = row.cells[0]?.trim() || ''

      // 获取方法定义
      let methodDef = null
      let methodColIndex = 0

      if (isVariable(firstCell)) {
        // 第一列是变量
        if (row.cells.length > 1) {
          const secondCell = row.cells[1]?.trim() || ''
          methodDef = getMethodDefinition(secondCell)
          methodColIndex = 1
        }
      } else if (isMethod(firstCell)) {
        // 第一列是方法
        methodDef = getMethodDefinition(firstCell)
        methodColIndex = 0
      }

      if (!methodDef || methodDef.params === -1) {
        return false // 没有方法定义或可变参数，不禁用
      }

      // 计算应该有多少个单元格
      const expectedCells = methodColIndex + 1 + methodDef.params

      // 如果是方法名所在的列，不禁用
      if (colIndex === methodColIndex) {
        return false
      }

      // 如果列索引超过了预期单元格数量，禁用
      if (colIndex >= expectedCells) {
        return true
      }

      return false
    }

    // 查询建议
    const querySuggestions = (queryString, cb, rowIndex, colIndex) => {
      const row = state.tableData[rowIndex]
      if (!row) {
        cb([])
        return
      }

      const currentValue = row.cells[colIndex]?.trim() || ''

      // 确定要显示哪种类型的建议
      let showVariables = false

      if (colIndex === 0) {
        // 第一列：如果当前输入以$开头，显示变量列表，否则显示方法列表
        showVariables = currentValue.startsWith('$') || queryString.startsWith('$')
      } else {
        // 其他列：根据第一列的内容决定
        const firstCell = row.cells[0]?.trim() || ''
        if (isVariable(firstCell)) {
          // 第一列是变量
          if (colIndex === 1) {
            // 第二列显示方法列表
            showVariables = false
          } else {
            // 其他列显示变量列表
            showVariables = true
          }
        } else if (isMethod(firstCell)) {
          // 第一列是方法，其他列显示变量列表
          showVariables = true
        } else {
          // 第一列既不是变量也不是方法，默认显示方法列表
          showVariables = false
        }
      }

      if (showVariables) {
        queryVariableSuggestions(queryString, cb)
      } else {
        queryMethodSuggestions(queryString, cb)
      }
    }

    // 查询变量建议
    const queryVariableSuggestions = (queryString, cb) => {
      const results = queryString
        ? state.variableDefinitions
            .filter(v =>
              v.name.toLowerCase().includes(queryString.toLowerCase()) ||
              v.description.toLowerCase().includes(queryString.toLowerCase())
            )
            .map(v => ({
              ...v,
              type: 'variable'
            }))
        : state.variableDefinitions.map(v => ({
            ...v,
            type: 'variable'
          }))
      cb(results)
    }

    // 查询方法建议
    const queryMethodSuggestions = (queryString, cb) => {
      const results = queryString
        ? Object.entries(state.methodDefinitions)
            .filter(([name]) => name.toLowerCase().includes(queryString.toLowerCase()))
            .map(([name, def]) => ({
              name,
              description: def.description,
              params: def.params,
              type: 'method'
            }))
        : Object.entries(state.methodDefinitions).map(([name, def]) => ({
            name,
            description: def.description,
            params: def.params,
            type: 'method'
          }))
      cb(results)
    }

    // 处理选择建议
    const handleSelectSuggestion = (rowIndex, colIndex, item) => {
      const row = state.tableData[rowIndex]
      if (row) {
        row.cells[colIndex] = item.name
        validateRow(rowIndex)
      }
    }

    // 处理单元格输入
    const handleCellInput = (rowIndex, colIndex) => {
      // 如果是第一列或第二列，更新验证
      if (colIndex === 0 || colIndex === 1) {
        validateRow(rowIndex)
      }
    }

    // 验证行的结构
    const validateRow = (rowIndex) => {
      const row = state.tableData[rowIndex]
      if (!row || row.cells.length === 0) {
        row.isValid = false
        return
      }

      const firstCell = row.cells[0]?.trim() || ''

      // 情况1: 第一列是变量
      if (isVariable(firstCell)) {
        if (row.cells.length < 2) {
          row.isValid = false
          return
        }

        const secondCell = row.cells[1]?.trim() || ''
        const methodDef = getMethodDefinition(secondCell)

        if (!methodDef) {
          row.isValid = false
          return
        }

        // 检查参数数量是否匹配
        const expectedCells = 2 + methodDef.params
        if (row.cells.length < expectedCells) {
          // 自动补齐缺失的单元格
          while (row.cells.length < expectedCells) {
            row.cells.push('')
          }
        } else if (row.cells.length > expectedCells && methodDef.params !== -1) {
          // 自动移除多余的单元格（只保留必要的）
          row.cells.splice(expectedCells)
        }

        row.isValid = true
      }
      // 情况2: 第一列是方法名
      else if (isMethod(firstCell)) {
        const methodDef = getMethodDefinition(firstCell)

        if (!methodDef) {
          row.isValid = false
          return
        }

        // 检查参数数量是否匹配
        const expectedCells = 1 + methodDef.params
        if (row.cells.length < expectedCells) {
          // 自动补齐缺失的单元格
          while (row.cells.length < expectedCells) {
            row.cells.push('')
          }
        } else if (row.cells.length > expectedCells && methodDef.params !== -1) {
          // 自动移除多余的单元格（只保留必要的）
          row.cells.splice(expectedCells)
        }

        row.isValid = true
      }
      // 情况3: 格式不正确
      else {
        row.isValid = false
      }
    }

    // 列管理相关方法
    const removeColumn = (colIndex) => {
      if (state.columnHeaders.length <= 1) {
        ElMessage.warning('至少需要保留一列')
        return
      }

      // 删除列标题
      state.columnHeaders.splice(colIndex, 1)

      // 删除每行对应的单元格
      state.tableData.forEach(row => {
        if (row.cells.length > colIndex) {
          row.cells.splice(colIndex, 1)
        }
      })

      // 重新验证所有行
      state.tableData.forEach((row, index) => {
        validateRow(index)
      })

      ElMessage.success('列删除成功')
    }

    const deleteEmptyColumns = () => {
      // 找出所有行的空列索引
      const emptyColumnIndices = new Set()

      state.tableData.forEach(row => {
        row.cells.forEach((cell, colIndex) => {
          if (!cell?.trim() && colIndex < state.columnHeaders.length) {
            emptyColumnIndices.add(colIndex)
          }
        })
      })

      // 从后往前删除空列
      const sortedIndices = Array.from(emptyColumnIndices).sort((a, b) => b - a)
      sortedIndices.forEach(colIndex => {
        if (state.columnHeaders.length > 1) {
          removeColumn(colIndex)
        }
      })

      if (sortedIndices.length > 0) {
        ElMessage.success(`已删除 ${sortedIndices.length} 个空列`)
      } else {
        ElMessage.info('未找到空列')
      }
    }

    const handleColumnCommand = (command) => {
      if (command === 'deleteEmptyColumns') {
        deleteEmptyColumns()
      } else if (command.type === 'delete') {
        removeColumn(command.index)
      }
      console.log(state.tableData);
    }

    // 添加新行
    const addRow = () => {
      state.tableData.push({
        cells: [''],
        isValid: false
      });
      console.log(state.tableData)
    }

    // 添加新列
    const addColumn = () => {
      state.columnHeaders.push(`单元格${state.columnHeaders.length + 1}`)
      // 为新列添加默认值
      state.tableData.forEach(row => {
        if (row.cells.length < state.columnHeaders.length) {
          row.cells.push('')
        }
        validateRow(state.tableData.indexOf(row))
      })
    }

    // 删除行
    const removeRow = (rowIndex) => {
      state.tableData.splice(rowIndex, 1)
    }

    // 重置表格
    const resetTable = () => {
      state.tableData = [{ cells: [''], isValid: false }]
      state.columnHeaders = ['单元格1']
    }

    const tableRowClassName = ({ rowIndex }) => {
      const row = state.tableData[rowIndex]
      return row && !row.isValid ? 'invalid-row' : ''
    }

    // 初始化变量数据
    const initVariableDefinitions = () => {
      state.variableDefinitions = [
        {
          name: '${screenshot1}',
          description: '登录页面截图',
          category: 'image',
          image: {
            url: 'https://via.placeholder.com/150/FF5733/FFFFFF?text=Login',
            thumbnail: 'https://via.placeholder.com/50/FF5733/FFFFFF?text=L',
            size: 102400
          },
          example: 'Take Screenshot    login_page.png'
        },
        {
          name: '${screenshot2}',
          description: '仪表板截图',
          category: 'image',
          image: {
            url: 'https://via.placeholder.com/150/33FF57/FFFFFF?text=Dash',
            thumbnail: 'https://via.placeholder.com/50/33FF57/FFFFFF?text=D',
            size: 153600
          },
          example: 'Take Screenshot    dashboard.png'
        },
        {
          name: '${user_avatar}',
          description: '用户头像图片',
          category: 'image',
          image: {
            url: 'https://via.placeholder.com/150/3357FF/FFFFFF?text=Avatar',
            thumbnail: 'https://via.placeholder.com/50/3357FF/FFFFFF?text=A',
            size: 51200
          },
          example: '${avatar}    Get Element Attribute    avatar_img    src'
        },
        {
          name: '${logo_image}',
          description: '网站Logo图片',
          category: 'image',
          image: {
            url: 'https://via.placeholder.com/150/FF33A1/FFFFFF?text=Logo',
            thumbnail: 'https://via.placeholder.com/50/FF33A1/FFFFFF?text=Logo',
            size: 20480
          },
          example: '${logo}    Capture Element Screenshot    id=logo'
        },
        {
          name: '${error_screenshot}',
          description: '错误页面截图',
          category: 'image',
          image: {
            url: 'https://via.placeholder.com/150/FF3333/FFFFFF?text=Error',
            thumbnail: 'https://via.placeholder.com/50/FF3333/FFFFFF?text=E',
            size: 256000
          },
          example: 'Take Screenshot On Failure'
        },
        {
          name: '${username}',
          description: '当前登录用户名',
          category: 'text',
          example: 'admin'
        },
        {
          name: '${password}',
          description: '用户密码（已加密）',
          category: 'text',
          example: '********'
        },
        {
          name: '${email}',
          description: '用户邮箱地址',
          category: 'text',
          example: 'user@example.com'
        },
        {
          name: '${api_response}',
          description: 'API接口返回的JSON数据',
          category: 'data',
          example: '{"status": "success", "data": {}}'
        },
        {
          name: '${user_list}',
          description: '用户列表数据',
          category: 'data',
          example: '["user1", "user2", "user3"]'
        },
        {
          name: '${current_date}',
          description: '当前系统日期',
          category: 'data',
          example: '2024-01-15'
        },
        {
          name: '${element_count}',
          description: '页面元素数量',
          category: 'data',
          example: '42'
        },
        {
          name: '${result}',
          description: '方法执行结果',
          category: 'text',
          example: '${result}    Get Text    id=element'
        },
        {
          name: '${value}',
          description: '通用值变量',
          category: 'text',
          example: '${value}    Get Value    id=input'
        },
        {
          name: '${condition}',
          description: '条件判断变量',
          category: 'data',
          example: '${condition}    Evaluate    ${var1} == ${var2}'
        }
      ]
    }

    // 初始化
    onMounted(() => {
      initVariableDefinitions()
      // 初始化验证
      state.tableData.forEach((row, index) => {
        validateRow(index)
      })
    })

    return {
      ...toRefs(state),
      invalidRowsCount,
      hasExtraColumns,
      formatAsRobotFramework,
      truncateDescription,
      truncateCellValue,
      getVariableIcon,
      getVariableIconColor,
      getCategoryTagType,
      getCategoryName,
      isVariable,
      isMethod,
      getMethodDefinition,
      getMethodDescription,
      getCellClass,
      getExtraCellClass,
      getCellTitle,
      getPlaceholder,
      getPopperClass,
      isCellDisabled,
      querySuggestions,
      handleSelectSuggestion,
      handleCellInput,
      validateRow,
      removeColumn,
      deleteEmptyColumns,
      handleColumnCommand,
      addRow,
      addColumn,
      removeRow,
      resetTable,
      tableRowClassName
    }
  }
}
</script>

<style scoped>
.rf-editor-container {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.control-bar {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f5f5;
  border-radius: 5px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.method-list {
  flex: 1;
  padding: 10px;
  background-color: #e8f5e8;
  border-radius: 4px;
}

.method-label {
  font-weight: bold;
  margin-right: 10px;
}

.method-tag {
  margin: 2px 5px;
  cursor: help;
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.delete-column-btn {
  margin-left: 8px;
  opacity: 0.5;
}

.delete-column-btn:hover {
  opacity: 1;
  color: #f56c6c;
}

.column-dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 180px;
}

.method-detail-popover {
  padding: 5px;
}

.method-detail-popover h4 {
  margin: 0 0 8px 0;
  color: #409eff;
}

.method-detail-popover p {
  margin: 4px 0;
  font-size: 13px;
  line-height: 1.4;
}

.method-detail-popover strong {
  color: #606266;
}

/* 增强下拉项样式 */
.suggestion-item {
  padding: 8px 12px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.suggestion-item:hover {
  background-color: #f5f7fa;
}

.suggestion-variable {
  display: flex;
  align-items: center;
  gap: 12px;
}

.variable-image-container {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
}

.variable-image-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
}

.image-error {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f5f5;
  color: #909399;
  border-radius: 4px;
}

.variable-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f5f5;
  border-radius: 4px;
}

.suggestion-content {
  flex: 1;
  min-width: 0;
}

.suggestion-main {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
  gap: 8px;
}

.suggestion-main strong {
  font-size: 14px;
  color: #409eff;
}

.suggestion-params {
  font-size: 12px;
  color: #909399;
  background: #f4f4f5;
  padding: 1px 6px;
  border-radius: 3px;
}

.suggestion-desc {
  font-size: 12px;
  color: #666;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.suggestion-method {
  display: flex;
  align-items: center;
}

/* 额外单元格样式优化 */
.extra-cells {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.extra-cell-tag {
  margin: 2px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: default;
}

.preview-section {
  margin-top: 30px;
  padding: 20px;
  background-color: #f8f9fa;
  border-radius: 5px;
  border: 1px solid #dee2e6;
}

.preview-section h3 {
  margin-top: 0;
  color: #333;
  margin-bottom: 10px;
}

.code-preview {
  background-color: #2d2d2d;
  color: #f8f8f2;
  padding: 15px;
  border-radius: 5px;
  overflow-x: auto;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.5;
  margin: 0;
}

/* 单元格样式 */
.cell-autocomplete {
  width: 100%;
}

.cell-variable :deep(.el-input__inner) {
  background-color: #e3f2fd !important;
  font-weight: bold;
  border-color: #90caf9;
}

.cell-method :deep(.el-input__inner) {
  background-color: #e8f5e8 !important;
  font-weight: bold;
  border-color: #a5d6a7;
}

.cell-param :deep(.el-input__inner) {
  background-color: #fff3e0 !important;
  border-color: #ffcc80;
}

.cell-param-disabled {
  background-color: #f5f5f5 !important;
  color: #999 !important;
  cursor: not-allowed;
}

/* 无效行样式 */
:deep(.invalid-row) {
  background-color: #ffebee !important;
}

:deep(.invalid-row:hover) {
  background-color: #ffcdd2 !important;
}

/* 禁用状态的输入框 */
:deep(.el-input.is-disabled .el-input__inner) {
  background-color: #f5f5f5 !important;
  color: #999 !important;
  border-color: #e4e7ed !important;
  cursor: not-allowed !important;
}

/* 下拉框样式优化 */
:deep(.method-popper .el-autocomplete-suggestion__list) {
  max-height: 300px !important;
}

:deep(.variable-popper .el-autocomplete-suggestion__list) {
  max-height: 400px !important;
}
</style>