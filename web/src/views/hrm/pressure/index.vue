<template>
  <div class="app-container pressure-page">
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="压测场景" name="scenario">
        <el-form :model="scenarioQuery" ref="scenarioQueryRef" :inline="true" v-show="showSearch">
          <el-form-item label="所属项目" prop="projectId">
            <el-select
                v-model="scenarioQuery.projectId"
                placeholder="请选择项目"
                clearable
                filterable
                style="width: 220px"
                @change="handleScenarioQueryProjectChange"
            >
              <el-option
                  v-for="item in projectOptions"
                  :key="item.projectId"
                  :label="item.projectName"
                  :value="item.projectId"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="所属模块" prop="moduleId">
            <el-select
                v-model="scenarioQuery.moduleId"
                placeholder="请选择模块"
                clearable
                filterable
                style="width: 220px"
            >
              <el-option
                  v-for="item in scenarioQueryModuleOptions"
                  :key="item.moduleId"
                  :label="item.moduleName"
                  :value="item.moduleId"
              />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" icon="Search" @click="getScenarioList">搜索</el-button>
            <el-button icon="Refresh" @click="resetScenarioQuery">重置</el-button>
          </el-form-item>
        </el-form>

        <el-row :gutter="10" class="mb8">
          <el-col :span="1.5">
            <el-button
                type="primary"
                plain
                icon="Plus"
                @click="handleAddScenario"
                v-hasPermi="['hrm:pressure:scenario:add']"
            >新增场景</el-button>
          </el-col>
          <right-toolbar v-model:showSearch="showSearch" @queryTable="getScenarioList"></right-toolbar>
        </el-row>

        <el-table
            v-loading="loading.scenario"
            :data="scenarioList"
            border
            table-layout="fixed"
            max-height="calc(100vh - 300px)"
        >
          <el-table-column label="ID" prop="id" width="90" />
          <el-table-column label="场景名称" prop="name" min-width="180" show-overflow-tooltip />
          <el-table-column label="项目ID" prop="projectId" width="110" />
          <el-table-column label="模块ID" prop="moduleId" width="110" />
          <el-table-column label="引擎" prop="engine" width="100" />
          <el-table-column label="Base URL" prop="baseUrl" min-width="220" show-overflow-tooltip />
          <el-table-column label="备注" prop="remark" min-width="160" show-overflow-tooltip />
          <el-table-column label="创建时间" prop="createTime" width="165">
            <template #default="scope">
              <span>{{ parseTime(scope.row.createTime) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="210" align="center" fixed="right">
            <template #default="scope">
              <el-button
                  link
                  type="primary"
                  icon="Edit"
                  title="编辑"
                  @click="handleEditScenario(scope.row)"
                  v-hasPermi="['hrm:pressure:scenario:edit', 'hrm:pressure:scenario:detail']"
              />
              <el-button
                  link
                  type="success"
                  icon="VideoPlay"
                  title="创建运行"
                  @click="handleCreateRun(scope.row)"
                  v-hasPermi="['hrm:pressure:run:add']"
              />
              <el-button
                  link
                  type="info"
                  icon="Tickets"
                  title="查看历史"
                  @click="showScenarioRuns(scope.row)"
                  v-hasPermi="['hrm:pressure:list']"
              />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="运行记录" name="run">
        <el-form :model="runQuery" ref="runQueryRef" :inline="true" v-show="showSearch">
          <el-form-item label="场景ID" prop="scenarioId">
            <el-input
                v-model="runQuery.scenarioId"
                placeholder="请输入场景ID"
                clearable
                style="width: 180px"
                @keyup.enter="getRunList"
            />
          </el-form-item>
          <el-form-item label="条数" prop="limit">
            <el-input-number v-model="runQuery.limit" :min="1" :max="200" controls-position="right" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" icon="Search" @click="getRunList">搜索</el-button>
            <el-button icon="Refresh" @click="resetRunQuery">重置</el-button>
          </el-form-item>
        </el-form>

        <el-row :gutter="10" class="mb8">
          <el-col :span="1.5">
            <el-button
                type="primary"
                plain
                icon="Plus"
                @click="handleCreateRun()"
                v-hasPermi="['hrm:pressure:run:add']"
            >创建运行</el-button>
          </el-col>
          <el-col :span="1.5">
            <el-button
                type="success"
                plain
                icon="DataAnalysis"
                :disabled="selectedRunIds.length < 2"
                @click="handleCompareRuns"
                v-hasPermi="['hrm:pressure:run:compare']"
            >历史对比</el-button>
          </el-col>
          <right-toolbar v-model:showSearch="showSearch" @queryTable="getRunList"></right-toolbar>
        </el-row>

        <el-table
            v-loading="loading.run"
            :data="runList"
            border
            table-layout="fixed"
            max-height="calc(100vh - 300px)"
            @selection-change="handleRunSelectionChange"
        >
          <el-table-column type="selection" width="50" align="center" />
          <el-table-column label="运行ID" prop="id" width="90" />
          <el-table-column label="场景ID" prop="scenarioId" width="90" />
          <el-table-column label="状态" prop="status" width="110">
            <template #default="scope">
              <el-tag :type="runStatusTag(scope.row.status)">{{ scope.row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="并发" prop="userCount" width="90" />
          <el-table-column label="启动速率" prop="spawnRate" width="100" />
          <el-table-column label="时长" prop="runTime" width="90" />
          <el-table-column label="Worker模式" prop="workerMode" width="110" />
          <el-table-column label="RPS" width="90">
            <template #default="scope">
              {{ formatMetric(scope.row.summary?.rps) }}
            </template>
          </el-table-column>
          <el-table-column label="平均RT(ms)" width="120">
            <template #default="scope">
              {{ formatMetric(scope.row.summary?.avgRtMs || scope.row.summary?.avg_rt_ms) }}
            </template>
          </el-table-column>
          <el-table-column label="P95(ms)" width="100">
            <template #default="scope">
              {{ formatMetric(scope.row.summary?.p95Ms || scope.row.summary?.p95_ms) }}
            </template>
          </el-table-column>
          <el-table-column label="失败率" width="90">
            <template #default="scope">
              {{ formatPercent(scope.row.summary?.failRate || scope.row.summary?.fail_rate) }}
            </template>
          </el-table-column>
          <el-table-column label="开始时间" prop="startAt" width="165">
            <template #default="scope">
              <span>{{ parseTime(scope.row.startAt) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260" align="center" fixed="right">
            <template #default="scope">
              <el-button
                  link
                  type="primary"
                  icon="View"
                  title="详情"
                  @click="handleRunDetail(scope.row)"
                  v-hasPermi="['hrm:pressure:run:detail']"
              />
              <el-button
                  link
                  type="success"
                  icon="VideoPlay"
                  title="启动"
                  :disabled="!canStart(scope.row.status)"
                  @click="handleStartRun(scope.row)"
                  v-hasPermi="['hrm:pressure:run:start']"
              />
              <el-button
                  link
                  type="warning"
                  icon="VideoPause"
                  title="停止"
                  :disabled="!canStop(scope.row.status)"
                  @click="handleStopRun(scope.row)"
                  v-hasPermi="['hrm:pressure:run:stop']"
              />
              <el-button
                  link
                  type="danger"
                  icon="CircleClose"
                  title="强制停止"
                  :disabled="!canStop(scope.row.status)"
                  @click="handleForceStopRun(scope.row)"
                  v-hasPermi="['hrm:pressure:run:stop']"
              />
              <el-button
                  link
                  type="info"
                  icon="Refresh"
                  title="刷新摘要"
                  @click="handleRefreshSummary(scope.row)"
                  v-hasPermi="['hrm:pressure:run:detail']"
              />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="Worker池" name="worker">
        <el-row :gutter="10" class="mb8">
          <el-col :span="1.5">
            <el-button
                type="primary"
                plain
                icon="Plus"
                @click="handleAddWorker"
                v-hasPermi="['hrm:pressure:worker:register']"
            >注册Worker</el-button>
          </el-col>
          <el-col :span="1.5">
            <el-checkbox v-model="workerQuery.includeUnhealthy" @change="getWorkerList">包含不健康节点</el-checkbox>
          </el-col>
          <right-toolbar v-model:showSearch="showSearch" @queryTable="getWorkerList"></right-toolbar>
        </el-row>

        <el-table
            v-loading="loading.worker"
            :data="workerList"
            border
            table-layout="fixed"
            max-height="calc(100vh - 250px)"
        >
          <el-table-column label="Worker ID" prop="workerId" min-width="160" show-overflow-tooltip />
          <el-table-column label="Host" prop="host" min-width="150" show-overflow-tooltip />
          <el-table-column label="状态" prop="status" width="100">
            <template #default="scope">
              <el-tag :type="workerStatusTag(scope.row.status)">{{ scope.row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最大用户" prop="maxUsers" width="100" />
          <el-table-column label="当前用户" prop="currentUsers" width="100" />
          <el-table-column label="CPU" width="90">
            <template #default="scope">
              {{ formatPercent(scope.row.cpuUsage) }}
            </template>
          </el-table-column>
          <el-table-column label="内存" width="90">
            <template #default="scope">
              {{ formatPercent(scope.row.memoryUsage) }}
            </template>
          </el-table-column>
          <el-table-column label="RPS" prop="rps" width="90" />
          <el-table-column label="失败率" width="90">
            <template #default="scope">
              {{ formatPercent(scope.row.failRate) }}
            </template>
          </el-table-column>
          <el-table-column label="占用运行" prop="busyRunId" width="100" />
          <el-table-column label="最后心跳" prop="lastHeartbeat" width="165">
            <template #default="scope">
              <span>{{ parseTime(scope.row.lastHeartbeat) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" align="center" fixed="right">
            <template #default="scope">
              <el-button
                  link
                  type="primary"
                  icon="Tickets"
                  title="任务"
                  @click="handleWorkerAssignment(scope.row)"
                  v-hasPermi="['hrm:pressure:worker:assignment']"
              />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog :title="scenarioDialogTitle" v-model="scenarioDialogOpen" width="82%" append-to-body destroy-on-close>
      <el-form ref="scenarioFormRef" :model="scenarioForm" :rules="scenarioRules" label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="场景名称" prop="name">
              <el-input v-model="scenarioForm.name" placeholder="请输入场景名称" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="所属项目" prop="projectId">
              <el-select
                  v-model="scenarioForm.projectId"
                  placeholder="请选择项目"
                  filterable
                  style="width: 100%"
                  @change="handleScenarioFormProjectChange"
              >
                <el-option
                    v-for="item in projectOptions"
                    :key="item.projectId"
                    :label="item.projectName"
                    :value="item.projectId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="所属模块" prop="moduleId">
              <el-select v-model="scenarioForm.moduleId" placeholder="请选择模块" filterable style="width: 100%">
                <el-option
                    v-for="item in scenarioFormModuleOptions"
                    :key="item.moduleId"
                    :label="item.moduleName"
                    :value="item.moduleId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="引擎" prop="engine">
              <el-select v-model="scenarioForm.engine" style="width: 100%">
                <el-option label="Locust" value="locust" />
                <el-option label="k6（预留）" value="k6" disabled />
                <el-option label="JMeter（预留）" value="jmeter" disabled />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="Base URL" prop="baseUrl">
              <el-input v-model="scenarioForm.baseUrl" placeholder="例如 http://127.0.0.1:8000" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="DSL配置">
              <div class="dsl-editor">
                <div class="dsl-toolbar">
                  <div class="dsl-wait">
                    <span>等待时间</span>
                    <el-input-number v-model="scenarioForm.dslModel.waitMin" :min="0" :step="0.1" controls-position="right" />
                    <span>~</span>
                    <el-input-number v-model="scenarioForm.dslModel.waitMax" :min="0" :step="0.1" controls-position="right" />
                    <span>秒</span>
                  </div>
                  <el-button type="primary" plain icon="Plus" @click="addDslTask">新增任务</el-button>
                </div>
                <div v-if="!scenarioForm.dslModel.tasks.length" class="editor-empty">暂无任务，请先新增任务</div>
                <div v-for="(task, taskIndex) in scenarioForm.dslModel.tasks" :key="task.rowKey" class="task-editor">
                  <div class="task-header">
                    <span>任务 {{ taskIndex + 1 }}</span>
                    <el-button link type="danger" icon="Delete" @click="removeDslTask(taskIndex)">删除任务</el-button>
                  </div>
                  <el-row :gutter="12">
                    <el-col :span="8">
                      <el-form-item label="名称" label-width="60px">
                        <el-input v-model="task.name" placeholder="任务名称" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="4">
                      <el-form-item label="权重" label-width="60px">
                        <el-input-number v-model="task.weight" :min="1" controls-position="right" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="4">
                      <el-form-item label="方法" label-width="60px">
                        <el-select v-model="task.method">
                          <el-option label="GET" value="GET" />
                          <el-option label="POST" value="POST" />
                          <el-option label="PUT" value="PUT" />
                          <el-option label="DELETE" value="DELETE" />
                          <el-option label="PATCH" value="PATCH" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="路径" label-width="60px">
                        <el-input v-model="task.url" placeholder="/api/demo/${id}" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="请求名" label-width="60px">
                        <el-input v-model="task.requestName" placeholder="Locust请求名（可选）" />
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <div class="assertion-title">
                    <span>断言</span>
                    <el-button link type="primary" icon="Plus" @click="addDslAssertion(taskIndex)">新增断言</el-button>
                  </div>
                  <el-table :data="task.assertions" border size="small" table-layout="fixed" max-height="220">
                    <el-table-column label="来源" width="170">
                      <template #default="scope">
                        <el-select v-model="scope.row.source" style="width: 100%">
                          <el-option label="status_code" value="status_code" />
                          <el-option label="text" value="text" />
                          <el-option label="JMESPath(body)" value="body" />
                        </el-select>
                      </template>
                    </el-table-column>
                    <el-table-column label="表达式(path)" min-width="180">
                      <template #default="scope">
                        <el-input
                            v-model="scope.row.path"
                            :disabled="scope.row.source !== 'body'"
                            placeholder="如 data.code"
                        />
                      </template>
                    </el-table-column>
                    <el-table-column label="运算符" width="140">
                      <template #default="scope">
                        <el-select v-model="scope.row.op" style="width: 100%">
                          <el-option label="==" value="==" />
                          <el-option label="!=" value="!=" />
                          <el-option label="in" value="in" />
                          <el-option label="contains" value="contains" />
                          <el-option label="regex" value="regex" />
                        </el-select>
                      </template>
                    </el-table-column>
                    <el-table-column label="期望值" min-width="180">
                      <template #default="scope">
                        <el-input v-model="scope.row.expected" placeholder="支持 JSON 或普通字符串" />
                      </template>
                    </el-table-column>
                    <el-table-column label="操作" width="80" align="center">
                      <template #default="scope">
                        <el-button link type="danger" icon="Delete" @click="removeDslAssertion(taskIndex, scope.$index)" />
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="CSV数据">
              <div class="csv-editor">
                <div class="csv-toolbar">
                  <el-button type="primary" plain icon="Plus" @click="addCsvRow">新增行</el-button>
                  <el-button plain icon="Plus" @click="addCsvColumn">新增列</el-button>
                  <el-button plain icon="Download" @click="downloadCsvTemplate">导出模板</el-button>
                  <el-button plain icon="Upload" @click="triggerCsvImport">导入CSV</el-button>
                  <input ref="csvFileInputRef" type="file" accept=".csv,text/csv" class="csv-file-input" @change="importCsvFile" />
                </div>
                <el-table :data="scenarioForm.csvRows" border size="small" table-layout="fixed" max-height="300">
                  <el-table-column
                      v-for="column in scenarioForm.csvHeaders"
                      :key="column"
                      :label="column"
                      min-width="180"
                  >
                    <template #header>
                      <div class="csv-header-cell">
                        <span>{{ column }}</span>
                        <el-button
                            v-if="scenarioForm.csvHeaders.length > 1"
                            link
                            type="danger"
                            icon="Close"
                            @click="removeCsvColumn(column)"
                        />
                      </div>
                    </template>
                    <template #default="scope">
                      <el-input v-model="scope.row[column]" placeholder="值" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="90" align="center" fixed="right">
                    <template #default="scope">
                      <el-button link type="danger" icon="Delete" @click="removeCsvRow(scope.$index)" />
                    </template>
                  </el-table-column>
                </el-table>
                <div v-if="!scenarioForm.csvRows.length" class="editor-empty">暂无 CSV 行数据，请新增或导入</div>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="scenarioForm.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="scenarioDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="loading.saveScenario" @click="submitScenario">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog :title="runDialogTitle" v-model="runDialogOpen" width="620px" append-to-body destroy-on-close>
      <el-form ref="runFormRef" :model="runForm" :rules="runRules" label-width="110px">
        <el-form-item label="场景ID" prop="scenarioId">
          <el-select v-model="runForm.scenarioId" filterable style="width: 100%" placeholder="请选择场景">
            <el-option
                v-for="item in scenarioList"
                :key="item.id"
                :label="`${item.id} - ${item.name}`"
                :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="并发用户" prop="users">
          <el-input-number v-model="runForm.users" :min="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="启动速率" prop="spawnRate">
          <el-input-number v-model="runForm.spawnRate" :min="0.1" :step="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="运行时长">
          <el-input v-model="runForm.runTime" placeholder="例如 30s、5m、1h；不填则手动停止" />
        </el-form-item>
        <el-form-item label="目标QPS">
          <el-input-number v-model="runForm.targetQps" :min="0" :step="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="Worker模式">
          <el-radio-group v-model="runForm.workerMode">
            <el-radio value="auto">自动选择</el-radio>
            <el-radio value="manual">手动选择</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="脚本分发">
          <el-select v-model="runForm.scriptDeliveryMode" style="width: 100%">
            <el-option label="共享目录" value="shared_path" />
            <el-option label="Worker拉取" value="fetch" />
            <el-option label="接口内联发送" value="inline" />
          </el-select>
        </el-form-item>
        <el-form-item label="Worker" v-if="runForm.workerMode === 'manual'" prop="workerIds">
          <el-select v-model="runForm.workerIds" multiple filterable style="width: 100%" placeholder="请选择空闲Worker">
            <el-option
                v-for="item in idleWorkers"
                :key="item.workerId"
                :label="`${item.workerId} (${item.host})`"
                :value="item.workerId"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="runDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="loading.saveRun" @click="submitRun">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog title="运行详情" v-model="runDetailOpen" width="78%" append-to-body destroy-on-close>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="运行ID">{{ runDetail.id }}</el-descriptions-item>
        <el-descriptions-item label="场景ID">{{ runDetail.scenarioId }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ runDetail.status }}</el-descriptions-item>
        <el-descriptions-item label="Master Web">{{ runDetail.masterWebPort }}</el-descriptions-item>
        <el-descriptions-item label="Master Port">{{ runDetail.masterBindPort }}</el-descriptions-item>
        <el-descriptions-item label="进程ID">{{ runDetail.masterPid }}</el-descriptions-item>
        <el-descriptions-item label="脚本路径" :span="3">{{ runDetail.scriptPath }}</el-descriptions-item>
        <el-descriptions-item label="报告路径" :span="3">{{ runDetail.reportPath }}</el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="3">{{ runDetail.errorMessage }}</el-descriptions-item>
      </el-descriptions>
      <el-divider content-position="left">摘要</el-divider>
      <pre class="json-preview">{{ formatJson(runDetail.summary || {}) }}</pre>
      <el-divider content-position="left" v-if="runDetail.locust">Locust 实时数据</el-divider>
      <pre class="json-preview" v-if="runDetail.locust">{{ formatJson(runDetail.locust) }}</pre>
    </el-dialog>

    <el-dialog title="历史对比" v-model="compareDialogOpen" width="78%" append-to-body destroy-on-close>
      <el-table :data="compareList" border table-layout="fixed">
        <el-table-column label="运行ID" prop="runId" width="90" />
        <el-table-column label="状态" prop="status" width="100" />
        <el-table-column label="并发" prop="users" width="90" />
        <el-table-column label="RPS" prop="rps" width="90" />
        <el-table-column label="平均RT(ms)" prop="avgRtMs" width="120" />
        <el-table-column label="P95(ms)" prop="p95Ms" width="100" />
        <el-table-column label="请求数" prop="requests" width="100" />
        <el-table-column label="失败数" prop="failures" width="100" />
        <el-table-column label="失败率" width="100">
          <template #default="scope">{{ formatPercent(scope.row.failRate) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog title="注册Worker" v-model="workerDialogOpen" width="620px" append-to-body destroy-on-close>
      <el-form ref="workerFormRef" :model="workerForm" :rules="workerRules" label-width="110px">
        <el-form-item label="Worker ID" prop="workerId">
          <el-input v-model="workerForm.workerId" placeholder="例如 worker-01" />
        </el-form-item>
        <el-form-item label="Host" prop="host">
          <el-input v-model="workerForm.host" placeholder="例如 10.0.0.11" />
        </el-form-item>
        <el-form-item label="主机名">
          <el-input v-model="workerForm.hostname" />
        </el-form-item>
        <el-form-item label="CPU核数">
          <el-input-number v-model="workerForm.cpuCores" :min="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="内存MB">
          <el-input-number v-model="workerForm.memoryMb" :min="128" controls-position="right" />
        </el-form-item>
        <el-form-item label="最大用户">
          <el-input-number v-model="workerForm.maxUsers" :min="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="支持引擎">
          <el-select v-model="workerForm.engineTypes" multiple style="width: 100%">
            <el-option label="locust" value="locust" />
            <el-option label="k6" value="k6" disabled />
            <el-option label="jmeter" value="jmeter" disabled />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select
              v-model="workerForm.labels"
              multiple
              filterable
              allow-create
              default-first-option
              style="width: 100%"
              placeholder="输入后回车"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="workerDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="loading.saveWorker" @click="submitWorker">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog title="Worker任务" v-model="assignmentDialogOpen" width="72%" append-to-body destroy-on-close>
      <pre class="json-preview">{{ formatJson(workerAssignment) }}</pre>
    </el-dialog>
  </div>
</template>

<script setup name="Pressure">
import {
  addPressureScenario,
  comparePressureRuns,
  createPressureRun,
  forceStopPressureRun,
  getPressureRunStatus,
  getPressureScenario,
  getPressureWorkerAssignment,
  listPressureRuns,
  listPressureScenarios,
  listPressureWorkers,
  refreshPressureSummary,
  registerPressureWorker,
  startPressureRun,
  stopPressureRun,
  updatePressureScenario
} from '@/api/hrm/pressure'
import { listProject } from '@/api/hrm/project'
import { selectModulList } from '@/api/hrm/module'
import { ElMessage, ElMessageBox } from 'element-plus'

const { proxy } = getCurrentInstance()

const activeTab = ref('scenario')
const showSearch = ref(true)
const scenarioList = ref([])
const projectOptions = ref([])
const runList = ref([])
const workerList = ref([])
const scenarioQueryModuleOptions = ref([])
const scenarioFormModuleOptions = ref([])
const selectedRunIds = ref([])
const compareList = ref([])
const runDetail = ref({})
const workerAssignment = ref({})
const csvFileInputRef = ref()

const scenarioDialogOpen = ref(false)
const runDialogOpen = ref(false)
const runDetailOpen = ref(false)
const compareDialogOpen = ref(false)
const workerDialogOpen = ref(false)
const assignmentDialogOpen = ref(false)
const scenarioDialogTitle = ref('新增场景')
const runDialogTitle = ref('创建运行')

const loading = ref({
  scenario: false,
  run: false,
  worker: false,
  saveScenario: false,
  saveRun: false,
  saveWorker: false
})

const scenarioQuery = ref({
  projectId: undefined,
  moduleId: undefined
})

const runQuery = ref({
  scenarioId: undefined,
  limit: 20
})

const workerQuery = ref({
  includeUnhealthy: false
})

const defaultDsl = {
  wait_time: {
    min: 0.1,
    max: 0.5
  },
  tasks: [
    {
      name: 'query_api',
      weight: 1,
      request: {
        method: 'GET',
        url: '/api/demo/${id}',
        name: '示例请求'
      },
      assertions: [
        {
          source: 'status_code',
          op: '==',
          expected: 200
        }
      ]
    }
  ]
}

const defaultCsvText = 'case\n{"name":"case_1","id":1,"assert":{"status_code":200}}\n'

function createAssertionModel() {
  return {
    source: 'status_code',
    path: '',
    op: '==',
    expected: '200',
    rowKey: `${Date.now()}_${Math.random()}`
  }
}

function createTaskModel(task = {}) {
  const request = task.request || {}
  const assertions = Array.isArray(task.assertions) ? task.assertions : []
  return {
    rowKey: `${Date.now()}_${Math.random()}`,
    name: task.name || request.name || '',
    weight: Number(task.weight || 1),
    method: (request.method || 'GET').toUpperCase(),
    url: request.url || request.path || '/',
    requestName: request.name || task.name || '',
    assertions: assertions.length
      ? assertions.map(item => ({
          source: item.source === 'status_code' || item.source === 'text' ? item.source : 'body',
          path: item.source === 'status_code' || item.source === 'text' ? '' : String(item.source || ''),
          op: item.op || '==',
          expected:
            typeof item.expected === 'string'
              ? item.expected
              : JSON.stringify(item.expected ?? ''),
          rowKey: `${Date.now()}_${Math.random()}`
        }))
      : [createAssertionModel()]
  }
}

function createDslModel(dsl = defaultDsl) {
  const waitTime = dsl?.wait_time || {}
  const tasks = Array.isArray(dsl?.tasks) ? dsl.tasks : []
  return {
    waitMin: Number(waitTime.min ?? 0.1),
    waitMax: Number(waitTime.max ?? 0.5),
    tasks: tasks.length ? tasks.map(item => createTaskModel(item)) : [createTaskModel()]
  }
}

const scenarioForm = ref({
  id: undefined,
  projectId: undefined,
  moduleId: undefined,
  name: '',
  engine: 'locust',
  baseUrl: '',
  dslModel: createDslModel(),
  csvHeaders: ['case'],
  csvRows: [{ case: '{"name":"case_1","id":1,"assert":{"status_code":200}}' }],
  remark: ''
})

const runForm = ref({
  scenarioId: undefined,
  users: 10,
  spawnRate: 1,
  runTime: '1m',
  targetQps: undefined,
  workerMode: 'auto',
  scriptDeliveryMode: 'shared_path',
  workerIds: []
})

const workerForm = ref({
  workerId: '',
  host: '',
  hostname: '',
  cpuCores: 1,
  memoryMb: 1024,
  maxUsers: 100,
  engineTypes: ['locust'],
  labels: []
})

const scenarioRules = {
  projectId: [{ required: true, message: '请选择项目', trigger: 'change' }],
  moduleId: [{ required: true, message: '请选择模块', trigger: 'change' }],
  name: [{ required: true, message: '场景名称不能为空', trigger: 'blur' }],
  engine: [{ required: true, message: '执行引擎不能为空', trigger: 'change' }]
}

const runRules = {
  scenarioId: [{ required: true, message: '请选择场景', trigger: 'change' }],
  users: [{ required: true, message: '请输入并发用户数', trigger: 'blur' }],
  spawnRate: [{ required: true, message: '请输入启动速率', trigger: 'blur' }]
}

const workerRules = {
  workerId: [{ required: true, message: 'Worker ID不能为空', trigger: 'blur' }],
  host: [{ required: true, message: 'Host不能为空', trigger: 'blur' }]
}

const idleWorkers = computed(() => workerList.value.filter(item => item.status === 'idle'))

function normalizeData(data) {
  return data || []
}

function normalizeScenario(item) {
  return {
    ...item,
    scenarioId: item.scenarioId ?? item.scenario_id,
    projectId: item.projectId ?? item.project_id,
    moduleId: item.moduleId ?? item.module_id,
    baseUrl: item.baseUrl ?? item.base_url,
    csvText: item.csvText ?? item.csv_text,
    createTime: item.createTime ?? item.create_time,
    updateTime: item.updateTime ?? item.update_time
  }
}

function normalizeRun(item) {
  return {
    ...item,
    projectId: item.projectId ?? item.project_id,
    scenarioId: item.scenarioId ?? item.scenario_id,
    userCount: item.userCount ?? item.user_count,
    spawnRate: item.spawnRate ?? item.spawn_rate,
    runTime: item.runTime ?? item.run_time,
    targetQps: item.targetQps ?? item.target_qps,
    workerMode: item.workerMode ?? item.worker_mode,
    scriptDeliveryMode: item.scriptDeliveryMode ?? item.script_delivery_mode,
    requestedWorkerIds: item.requestedWorkerIds ?? item.requested_worker_ids,
    allocatedWorkerIds: item.allocatedWorkerIds ?? item.allocated_worker_ids,
    masterHost: item.masterHost ?? item.master_host,
    masterWebPort: item.masterWebPort ?? item.master_web_port,
    masterBindPort: item.masterBindPort ?? item.master_bind_port,
    masterPid: item.masterPid ?? item.master_pid,
    artifactDir: item.artifactDir ?? item.artifact_dir,
    scriptPath: item.scriptPath ?? item.script_path,
    csvPath: item.csvPath ?? item.csv_path,
    reportPath: item.reportPath ?? item.report_path,
    errorMessage: item.errorMessage ?? item.error_message,
    startAt: item.startAt ?? item.start_at,
    endAt: item.endAt ?? item.end_at
  }
}

function normalizeWorker(item) {
  return {
    ...item,
    workerId: item.workerId ?? item.worker_id,
    cpuCores: item.cpuCores ?? item.cpu_cores,
    memoryMb: item.memoryMb ?? item.memory_mb,
    maxUsers: item.maxUsers ?? item.max_users,
    currentUsers: item.currentUsers ?? item.current_users,
    engineTypes: item.engineTypes ?? item.engine_types,
    cpuUsage: item.cpuUsage ?? item.cpu_usage,
    memoryUsage: item.memoryUsage ?? item.memory_usage,
    failRate: item.failRate ?? item.fail_rate,
    latencyMs: item.latencyMs ?? item.latency_ms,
    busyRunId: item.busyRunId ?? item.busy_run_id,
    lastHeartbeat: item.lastHeartbeat ?? item.last_heartbeat
  }
}

function normalizeCompare(item) {
  return {
    ...item,
    runId: item.runId ?? item.run_id,
    scenarioId: item.scenarioId ?? item.scenario_id,
    spawnRate: item.spawnRate ?? item.spawn_rate,
    avgRtMs: item.avgRtMs ?? item.avg_rt_ms,
    p95Ms: item.p95Ms ?? item.p95_ms,
    failRate: item.failRate ?? item.fail_rate,
    startAt: item.startAt ?? item.start_at,
    endAt: item.endAt ?? item.end_at
  }
}

function toNumberOrUndefined(value) {
  if (value === '' || value === null || value === undefined) return undefined
  const numberValue = Number(value)
  return Number.isNaN(numberValue) ? undefined : numberValue
}

function normalizeHeaderName(name, index) {
  const fallback = `column_${index + 1}`
  const header = String(name || '').trim()
  return header || fallback
}

function normalizeCsvHeaders(headers) {
  const dedup = new Set()
  const normalized = []
  headers.forEach((header, index) => {
    let nextName = normalizeHeaderName(header, index)
    let suffix = 1
    while (dedup.has(nextName)) {
      nextName = `${normalizeHeaderName(header, index)}_${suffix}`
      suffix += 1
    }
    dedup.add(nextName)
    normalized.push(nextName)
  })
  return normalized.length ? normalized : ['case']
}

function normalizeCsvRows(rows, headers) {
  return (rows || []).map(row => {
    const next = {}
    headers.forEach(header => {
      const value = row?.[header]
      next[header] = value === null || value === undefined ? '' : String(value)
    })
    return next
  })
}

function parseCsvRecords(text) {
  const source = String(text || '')
  const records = []
  let row = []
  let field = ''
  let inQuotes = false
  for (let i = 0; i < source.length; i += 1) {
    const char = source[i]
    if (char === '"') {
      if (inQuotes && source[i + 1] === '"') {
        field += '"'
        i += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }
    if (char === ',' && !inQuotes) {
      row.push(field)
      field = ''
      continue
    }
    if (char === '\n' && !inQuotes) {
      row.push(field)
      records.push(row)
      row = []
      field = ''
      continue
    }
    if (char === '\r' && !inQuotes) {
      continue
    }
    field += char
  }
  if (field !== '' || row.length > 0) {
    row.push(field)
    records.push(row)
  }
  return records
}

function parseCsvText(csvText) {
  const records = parseCsvRecords(String(csvText || '').replace(/^\uFEFF/, ''))
  if (!records.length) {
    return {
      headers: ['case'],
      rows: []
    }
  }
  const headers = normalizeCsvHeaders(records[0])
  const rows = records.slice(1).map(cells => {
    const row = {}
    headers.forEach((header, index) => {
      row[header] = cells[index] ?? ''
    })
    return row
  })
  return {
    headers,
    rows: normalizeCsvRows(rows, headers)
  }
}

function escapeCsvCell(value) {
  const text = value === null || value === undefined ? '' : String(value)
  if (text.includes(',') || text.includes('"') || text.includes('\n') || text.includes('\r')) {
    return `"${text.replaceAll('"', '""')}"`
  }
  return text
}

function buildCsvText(headers, rows) {
  const normalizedHeaders = normalizeCsvHeaders(headers || [])
  const normalizedRows = normalizeCsvRows(rows || [], normalizedHeaders)
  const lines = [normalizedHeaders.map(item => escapeCsvCell(item)).join(',')]
  normalizedRows.forEach(row => {
    lines.push(normalizedHeaders.map(header => escapeCsvCell(row[header])).join(','))
  })
  return `${lines.join('\n')}\n`
}

function parseExpectedValue(expectedText) {
  const text = String(expectedText ?? '').trim()
  if (text === '') {
    return ''
  }
  try {
    return JSON.parse(text)
  } catch {
    return expectedText
  }
}

function buildDslPayload(model) {
  const tasks = (model.tasks || []).map(task => {
    const assertions = (task.assertions || [])
      .filter(item => item.source && item.op)
      .map(item => ({
        source: item.source === 'body' ? String(item.path || '').trim() : item.source,
        op: item.op,
        expected: parseExpectedValue(item.expected)
      }))
      .filter(item => item.source)
    return {
      name: String(task.name || '').trim() || String(task.requestName || '').trim() || 'task',
      weight: Math.max(1, Number(task.weight || 1)),
      request: {
        method: String(task.method || 'GET').toUpperCase(),
        url: String(task.url || '/').trim() || '/',
        name: String(task.requestName || '').trim() || undefined
      },
      assertions
    }
  })
  return {
    wait_time: {
      min: Number(model.waitMin ?? 0.1),
      max: Number(model.waitMax ?? 0.5)
    },
    tasks
  }
}

function validateDslModel(model) {
  if (!model.tasks || !model.tasks.length) {
    ElMessage.warning('请至少配置一个压测任务')
    return false
  }
  if (Number(model.waitMin) > Number(model.waitMax)) {
    ElMessage.warning('等待时间最小值不能大于最大值')
    return false
  }
  for (let index = 0; index < model.tasks.length; index += 1) {
    const task = model.tasks[index]
    if (!String(task.url || '').trim()) {
      ElMessage.warning(`任务${index + 1}请求路径不能为空`)
      return false
    }
    for (let aIndex = 0; aIndex < (task.assertions || []).length; aIndex += 1) {
      const assertion = task.assertions[aIndex]
      if (assertion.source === 'body' && !String(assertion.path || '').trim()) {
        ElMessage.warning(`任务${index + 1}第${aIndex + 1}条断言缺少路径`)
        return false
      }
    }
  }
  return true
}

function getScenarioList() {
  loading.value.scenario = true
  listPressureScenarios({
    project_id: toNumberOrUndefined(scenarioQuery.value.projectId),
    module_id: toNumberOrUndefined(scenarioQuery.value.moduleId)
  }).then(response => {
    scenarioList.value = normalizeData(response.data).map(normalizeScenario)
  }).finally(() => {
    loading.value.scenario = false
  })
}

function getRunList() {
  loading.value.run = true
  listPressureRuns({
    scenario_id: toNumberOrUndefined(runQuery.value.scenarioId),
    limit: runQuery.value.limit
  }).then(response => {
    runList.value = normalizeData(response.data).map(normalizeRun)
  }).finally(() => {
    loading.value.run = false
  })
}

function getWorkerList() {
  loading.value.worker = true
  listPressureWorkers({
    include_unhealthy: workerQuery.value.includeUnhealthy
  }).then(response => {
    workerList.value = normalizeData(response.data).map(normalizeWorker)
  }).finally(() => {
    loading.value.worker = false
  })
}

function resetScenarioQuery() {
  scenarioQuery.value.projectId = undefined
  scenarioQuery.value.moduleId = undefined
  scenarioQueryModuleOptions.value = []
  getScenarioList()
}

function resetRunQuery() {
  runQuery.value.scenarioId = undefined
  runQuery.value.limit = 20
  getRunList()
}

function handleTabChange(name) {
  if (name === 'scenario') getScenarioList()
  if (name === 'run') getRunList()
  if (name === 'worker') getWorkerList()
}

function resetScenarioForm() {
  scenarioForm.value = {
    id: undefined,
    projectId: undefined,
    moduleId: undefined,
    name: '',
    engine: 'locust',
    baseUrl: '',
    dslModel: createDslModel(),
    csvHeaders: ['case'],
    csvRows: [{ case: '{"name":"case_1","id":1,"assert":{"status_code":200}}' }],
    remark: ''
  }
  scenarioFormModuleOptions.value = []
}

function handleAddScenario() {
  resetScenarioForm()
  scenarioDialogTitle.value = '新增场景'
  scenarioDialogOpen.value = true
}

function handleEditScenario(row) {
  getPressureScenario(row.id).then(response => {
    const data = normalizeScenario(response.data || {})
    const csvModel = parseCsvText(data.csvText || defaultCsvText)
    loadScenarioFormModules(data.projectId)
    scenarioForm.value = {
      id: data.id,
      projectId: data.projectId,
      moduleId: data.moduleId,
      name: data.name || '',
      engine: data.engine || 'locust',
      baseUrl: data.baseUrl || '',
      dslModel: createDslModel(data.dsl || defaultDsl),
      csvHeaders: csvModel.headers,
      csvRows: csvModel.rows,
      remark: data.remark || ''
    }
    scenarioDialogTitle.value = `编辑场景 ${data.id}`
    scenarioDialogOpen.value = true
  })
}

function submitScenario() {
  proxy.$refs.scenarioFormRef.validate(valid => {
    if (!valid) return
    if (!validateDslModel(scenarioForm.value.dslModel)) {
      return
    }
    const dsl = buildDslPayload(scenarioForm.value.dslModel)
    const csvText = buildCsvText(scenarioForm.value.csvHeaders, scenarioForm.value.csvRows)
    const payload = {
      project_id: scenarioForm.value.projectId,
      module_id: scenarioForm.value.moduleId,
      name: scenarioForm.value.name,
      engine: scenarioForm.value.engine,
      base_url: scenarioForm.value.baseUrl,
      dsl,
      csv_text: csvText,
      remark: scenarioForm.value.remark
    }
    loading.value.saveScenario = true
    const request = scenarioForm.value.id
      ? updatePressureScenario(scenarioForm.value.id, payload)
      : addPressureScenario(payload)
    request.then(() => {
      proxy.$modal.msgSuccess('保存成功')
      scenarioDialogOpen.value = false
      getScenarioList()
    }).finally(() => {
      loading.value.saveScenario = false
    })
  })
}

function addDslTask() {
  scenarioForm.value.dslModel.tasks.push(createTaskModel())
}

function removeDslTask(taskIndex) {
  scenarioForm.value.dslModel.tasks.splice(taskIndex, 1)
}

function addDslAssertion(taskIndex) {
  scenarioForm.value.dslModel.tasks[taskIndex].assertions.push(createAssertionModel())
}

function removeDslAssertion(taskIndex, assertionIndex) {
  scenarioForm.value.dslModel.tasks[taskIndex].assertions.splice(assertionIndex, 1)
}

function addCsvRow() {
  const row = {}
  scenarioForm.value.csvHeaders.forEach(header => {
    row[header] = ''
  })
  scenarioForm.value.csvRows.push(row)
}

async function addCsvColumn() {
  let value
  try {
    ;({ value } = await ElMessageBox.prompt('请输入列名', '新增CSV列', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '列名不能为空'
    }))
  } catch {
    return
  }
  const name = String(value || '').trim()
  if (!name) {
    return
  }
  if (scenarioForm.value.csvHeaders.includes(name)) {
    ElMessage.warning('列名已存在')
    return
  }
  scenarioForm.value.csvHeaders.push(name)
  scenarioForm.value.csvRows.forEach(row => {
    row[name] = ''
  })
}

function removeCsvColumn(columnName) {
  if (scenarioForm.value.csvHeaders.length <= 1) {
    ElMessage.warning('至少保留一列')
    return
  }
  scenarioForm.value.csvHeaders = scenarioForm.value.csvHeaders.filter(item => item !== columnName)
  scenarioForm.value.csvRows = scenarioForm.value.csvRows.map(row => {
    const nextRow = { ...row }
    delete nextRow[columnName]
    return nextRow
  })
}

function removeCsvRow(index) {
  scenarioForm.value.csvRows.splice(index, 1)
}

function triggerCsvImport() {
  if (csvFileInputRef.value) {
    csvFileInputRef.value.click()
  }
}

async function importCsvFile(event) {
  const file = event?.target?.files?.[0]
  if (!file) {
    return
  }
  try {
    const text = await file.text()
    const csvModel = parseCsvText(text)
    scenarioForm.value.csvHeaders = csvModel.headers
    scenarioForm.value.csvRows = csvModel.rows
    ElMessage.success('CSV导入成功')
  } catch (error) {
    ElMessage.error(`CSV导入失败：${error.message}`)
  } finally {
    if (csvFileInputRef.value) {
      csvFileInputRef.value.value = ''
    }
  }
}

function downloadCsvTemplate() {
  const csvText =
    scenarioForm.value.csvHeaders.length === 1 && scenarioForm.value.csvHeaders[0] === 'case'
      ? defaultCsvText
      : buildCsvText(scenarioForm.value.csvHeaders, [])
  const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'pressure-template.csv'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function loadProjectOptions() {
  return listProject({ isPage: false }).then(response => {
    projectOptions.value = normalizeData(response.data)
  })
}

function loadScenarioQueryModules(projectId) {
  if (!projectId) {
    scenarioQueryModuleOptions.value = []
    return Promise.resolve()
  }
  return selectModulList({ projectId }).then(response => {
    scenarioQueryModuleOptions.value = normalizeData(response.data)
  })
}

function loadScenarioFormModules(projectId) {
  if (!projectId) {
    scenarioFormModuleOptions.value = []
    return Promise.resolve()
  }
  return selectModulList({ projectId }).then(response => {
    scenarioFormModuleOptions.value = normalizeData(response.data)
  })
}

function handleScenarioQueryProjectChange(projectId) {
  scenarioQuery.value.moduleId = undefined
  loadScenarioQueryModules(projectId)
}

function handleScenarioFormProjectChange(projectId) {
  scenarioForm.value.moduleId = undefined
  loadScenarioFormModules(projectId)
}

function resetRunForm(scenario) {
  runForm.value = {
    scenarioId: scenario?.id,
    users: 10,
    spawnRate: 1,
    runTime: '1m',
    targetQps: undefined,
    workerMode: 'auto',
    scriptDeliveryMode: 'shared_path',
    workerIds: []
  }
}

function handleCreateRun(scenario) {
  resetRunForm(scenario)
  runDialogTitle.value = scenario ? `创建运行 - ${scenario.name}` : '创建运行'
  runDialogOpen.value = true
  if (!workerList.value.length) getWorkerList()
}

function submitRun() {
  proxy.$refs.runFormRef.validate(valid => {
    if (!valid) return
    if (runForm.value.workerMode === 'manual' && !runForm.value.workerIds.length) {
      ElMessage.warning('手动模式必须选择至少一个Worker')
      return
    }
    const payload = {
      scenario_id: runForm.value.scenarioId,
      users: runForm.value.users,
      spawn_rate: runForm.value.spawnRate,
      run_time: runForm.value.runTime || undefined,
      target_qps: runForm.value.targetQps || undefined,
      worker_mode: runForm.value.workerMode,
      script_delivery_mode: runForm.value.scriptDeliveryMode,
      worker_ids: runForm.value.workerIds
    }
    loading.value.saveRun = true
    createPressureRun(payload).then(() => {
      proxy.$modal.msgSuccess('创建成功')
      runDialogOpen.value = false
      activeTab.value = 'run'
      getRunList()
    }).finally(() => {
      loading.value.saveRun = false
    })
  })
}

function showScenarioRuns(row) {
  runQuery.value.scenarioId = row.id
  activeTab.value = 'run'
  getRunList()
}

function handleRunSelectionChange(selection) {
  selectedRunIds.value = selection.map(item => item.id)
}

function handleStartRun(row) {
  proxy.$modal.confirm(`确认启动运行 ${row.id}？`).then(() => startPressureRun(row.id)).then(() => {
    proxy.$modal.msgSuccess('已启动')
    getRunList()
  })
}

function handleStopRun(row) {
  proxy.$modal.confirm(`确认停止运行 ${row.id}？`).then(() => stopPressureRun(row.id)).then(() => {
    proxy.$modal.msgSuccess('已停止')
    getRunList()
    getWorkerList()
  })
}

function handleForceStopRun(row) {
  proxy.$modal.confirm(`确认强制停止运行 ${row.id}？`).then(() => forceStopPressureRun(row.id)).then(() => {
    proxy.$modal.msgSuccess('已强制停止')
    getRunList()
    getWorkerList()
  })
}

function handleRunDetail(row) {
  getPressureRunStatus(row.id).then(response => {
    runDetail.value = normalizeRun(response.data || {})
    runDetailOpen.value = true
  })
}

function handleRefreshSummary(row) {
  refreshPressureSummary(row.id).then(() => {
    proxy.$modal.msgSuccess('摘要已刷新')
    getRunList()
  })
}

function handleCompareRuns() {
  comparePressureRuns({ run_ids: selectedRunIds.value }).then(response => {
    compareList.value = (response.data || []).map(normalizeCompare)
    compareDialogOpen.value = true
  })
}

function handleAddWorker() {
  workerForm.value = {
    workerId: '',
    host: '',
    hostname: '',
    cpuCores: 1,
    memoryMb: 1024,
    maxUsers: 100,
    engineTypes: ['locust'],
    labels: []
  }
  workerDialogOpen.value = true
}

function submitWorker() {
  proxy.$refs.workerFormRef.validate(valid => {
    if (!valid) return
    const payload = {
      worker_id: workerForm.value.workerId,
      host: workerForm.value.host,
      hostname: workerForm.value.hostname,
      cpu_cores: workerForm.value.cpuCores,
      memory_mb: workerForm.value.memoryMb,
      max_users: workerForm.value.maxUsers,
      engine_types: workerForm.value.engineTypes,
      labels: workerForm.value.labels
    }
    loading.value.saveWorker = true
    registerPressureWorker(payload).then(() => {
      proxy.$modal.msgSuccess('注册成功')
      workerDialogOpen.value = false
      getWorkerList()
    }).finally(() => {
      loading.value.saveWorker = false
    })
  })
}

function handleWorkerAssignment(row) {
  getPressureWorkerAssignment(row.workerId).then(response => {
    workerAssignment.value = response.data || {}
    assignmentDialogOpen.value = true
  })
}

function canStart(status) {
  return ['pending', 'failed', 'canceled'].includes(status)
}

function canStop(status) {
  return ['starting', 'running', 'stopping'].includes(status)
}

function runStatusTag(status) {
  if (status === 'running') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'canceled') return 'info'
  if (status === 'starting' || status === 'stopping') return 'warning'
  if (status === 'finished') return 'info'
  return ''
}

function workerStatusTag(status) {
  if (status === 'idle') return 'success'
  if (status === 'busy') return 'warning'
  if (status === 'unhealthy') return 'danger'
  return ''
}

function formatMetric(value) {
  if (value === null || value === undefined || value === '') return '-'
  const numberValue = Number(value)
  if (Number.isNaN(numberValue)) return value
  return numberValue.toFixed(2)
}

function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '-'
  const numberValue = Number(value)
  if (Number.isNaN(numberValue)) return value
  return `${(numberValue * 100).toFixed(2)}%`
}

function formatJson(value) {
  return JSON.stringify(value || {}, null, 2)
}

onMounted(() => {
  loadProjectOptions()
  getScenarioList()
  getRunList()
  getWorkerList()
})
</script>

<style scoped>
.pressure-page :deep(.el-textarea__inner) {
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 13px;
}

.dsl-editor,
.csv-editor {
  width: 100%;
}

.dsl-toolbar,
.csv-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.dsl-wait {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-editor {
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}

.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-weight: 600;
}

.assertion-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4px 0 8px;
}

.csv-header-cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.csv-file-input {
  display: none;
}

.editor-empty {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  padding: 8px 0;
}

.json-preview {
  max-height: 420px;
  overflow: auto;
  padding: 12px;
  margin: 0;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background: var(--el-fill-color-lighter);
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
