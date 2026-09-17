<template>
  <el-dialog
    v-model="visible"
    :title="''"
    width="1280px"
    top="5vh"
    append-to-body
    destroy-on-close
    class="credential-dialog"
  >
    <div class="credential-editor">
      <div class="editor-head">
        <div class="editor-head-main">
          <div class="editor-kicker">统一凭证管理</div>
          <div class="editor-title">
            {{ form.credentialId ? '编辑凭证' : '新增凭证' }}
            <el-tag v-if="form.enabled" size="small" type="success">已启用</el-tag>
            <el-tag v-else size="small" type="info">已停用</el-tag>
          </div>
          <div class="editor-subtitle">
            配置凭证内容、认证流程和生命周期。现有后端字段与保存逻辑保持不变。
          </div>
        </div>
        <div class="editor-head-meta">
          <span v-if="form.credentialId">Revision {{ form.revision }}</span>
          <span v-else>新建凭证</span>
        </div>
      </div>

      <div class="editor-steps">
        <button
          v-for="item in [
            { key: 'basic', no: '1', title: '基本信息', desc: '名称与凭证类型' },
            { key: 'auth', no: '2', title: '认证方式', desc: '账号、OTP 与认证流程' },
            { key: 'request', no: '3', title: '获取 / 刷新', desc: '请求、断言与响应提取' },
            { key: 'lifecycle', no: '4', title: '生命周期', desc: '自动维护与使用策略' },
          ]"
          :key="item.key"
          type="button"
          class="editor-step"
          :class="{ active: activeSection === item.key }"
          @click="setSection(item.key)"
        >
          <span class="editor-step-no">{{ item.no }}</span>
          <span class="editor-step-copy">
            <b>{{ item.title }}</b>
            <small>{{ item.desc }}</small>
          </span>
        </button>
      </div>

      <div class="editor-body">
        <!-- 1. 基本信息 -->
        <section v-show="activeSection === 'basic'" class="editor-section">
          <div class="section-heading">
            <div>
              <h3>基本信息</h3>
              <p>先确定这份凭证是什么，以及它保存什么类型的认证信息。</p>
            </div>
          </div>

          <el-form :model="form" label-position="top" class="clean-form">
            <div class="field-card">
              <el-form-item label="凭证名称" required>
                <el-input
                  v-model="form.credentialName"
                  size="large"
                  placeholder="例如：ERP 生产环境登录凭证"
                  maxlength="100"
                  show-word-limit
                />
              </el-form-item>
            </div>

            <div class="field-card">
              <div class="field-label">凭证类型</div>
              <div class="choice-grid credential-type-grid">
                <button
                  v-for="item in credentialTypes"
                  :key="item.value"
                  type="button"
                  class="choice-card"
                  :class="{ active: form.credentialType === item.value }"
                  @click="form.credentialType = item.value"
                >
                  <span class="choice-radio"></span>
                  <span>
                    <b>{{ item.label }}</b>
                    <small>
                      {{
                        {
                          browser_storage: 'Playwright 浏览器会话状态',
                          http_cookie: 'Cookie 会话凭证',
                          http_token: 'JWT / Bearer 等 Token',
                          http_api_key: '固定 API Key',
                          http_header: '自定义 Header 凭证',
                        }[item.value]
                      }}
                    </small>
                  </span>
                </button>
              </div>
            </div>

            <div class="field-card">
              <div class="field-card-head">
                <div>
                  <div class="field-label">凭证内容</div>
                  <div class="field-hint">敏感值会按现有逻辑加密保存，编辑时支持掩码回显。</div>
                </div>
              </div>

              <template v-if="form.credentialType === 'http_cookie'">
                <el-form-item label="Cookie">
                  <el-input
                    v-model="sensitive.cookie"
                    type="textarea"
                    :rows="3"
                    placeholder="例如 SESSION=xxx; tenant=prod"
                  />
                </el-form-item>
              </template>

              <template
                v-else-if="
                  form.credentialType === 'http_header' || form.credentialType === 'http_api_key'
                "
              >
                <div class="two-col">
                  <el-form-item label="Header 名称">
                    <el-input
                      v-model="sensitive.headerName"
                      placeholder="例如 X-API-Key / Authorization"
                    />
                  </el-form-item>
                  <el-form-item label="Header 值">
                    <el-input
                      v-model="sensitive.headerValue"
                      type="password"
                      show-password
                      autocomplete="new-password"
                      placeholder="密钥或令牌内容"
                    />
                  </el-form-item>
                </div>
              </template>

              <template v-else-if="form.credentialType === 'http_token'">
                <div class="three-col">
                  <el-form-item label="Header 名称">
                    <el-input v-model="sensitive.headerName" placeholder="Authorization" />
                  </el-form-item>
                  <el-form-item label="值前缀">
                    <el-input v-model="sensitive.valuePrefix" placeholder="Bearer " />
                  </el-form-item>
                  <el-form-item label="Token">
                    <el-input
                      v-model="sensitive.token"
                      type="password"
                      show-password
                      autocomplete="new-password"
                      placeholder="Token 值"
                    />
                  </el-form-item>
                </div>
              </template>

              <template v-else>
                <el-form-item label="storageState">
                  <el-input
                    v-model="storageStateText"
                    type="textarea"
                    :rows="6"
                    placeholder='Playwright storageState，例如 {"cookies":[],"origins":[]}'
                  />
                </el-form-item>
              </template>
            </div>

            <div v-if="form.credentialType !== 'browser_storage'" class="advanced-card">
              <button
                type="button"
                class="advanced-head"
                @click="advancedVisible.basic = !advancedVisible.basic"
              >
                <span>
                  <b>附加认证信息</b>
                  <small>CSRF、租户 Header / Cookie、refreshToken 等固定敏感字段</small>
                </span>
                <span class="advanced-toggle">{{ advancedVisible.basic ? '收起' : '展开' }}</span>
              </button>

              <div v-show="advancedVisible.basic" class="advanced-body">
                <el-alert
                  v-if="hasCookieHeaderPrimary"
                  type="warning"
                  :closable="false"
                  show-icon
                  title="主 Header 已使用 Cookie，不能同时配置结构化附加 Cookie。"
                  class="compact-alert"
                />

                <el-form-item label="附加 Header">
                  <div class="kv-list">
                    <div
                      v-for="(item, index) in additionalHeaders"
                      :key="`header-${index}`"
                      class="kv-row"
                    >
                      <el-input v-model="item.name" placeholder="名称，例如 X-CSRF-Token" />
                      <el-input
                        v-model="item.value"
                        type="password"
                        show-password
                        autocomplete="new-password"
                        placeholder="值"
                      />
                      <el-button
                        :icon="Delete"
                        text
                        type="danger"
                        @click="additionalHeaders.splice(index, 1)"
                        >删除</el-button
                      >
                    </div>
                    <el-button
                      :icon="Plus"
                      plain
                      @click="additionalHeaders.push({ name: '', value: '' })"
                      >添加 Header</el-button
                    >
                  </div>
                </el-form-item>

                <el-form-item label="附加 Cookie">
                  <div class="kv-list">
                    <div
                      v-for="(item, index) in additionalCookies"
                      :key="`cookie-${index}`"
                      class="kv-row"
                    >
                      <el-input
                        v-model="item.name"
                        placeholder="名称，例如 CSRF-TOKEN"
                        :disabled="hasCookieHeaderPrimary"
                      />
                      <el-input
                        v-model="item.value"
                        type="password"
                        show-password
                        autocomplete="new-password"
                        placeholder="值"
                        :disabled="hasCookieHeaderPrimary"
                      />
                      <el-button
                        :icon="Delete"
                        text
                        type="danger"
                        @click="additionalCookies.splice(index, 1)"
                        >删除</el-button
                      >
                    </div>
                    <el-button
                      :icon="Plus"
                      plain
                      :disabled="hasCookieHeaderPrimary"
                      @click="additionalCookies.push({ name: '', value: '' })"
                      >添加 Cookie</el-button
                    >
                  </div>
                </el-form-item>

                <el-form-item label="其他敏感字段 JSON">
                  <el-input
                    v-model="advancedSecretText"
                    type="textarea"
                    :rows="4"
                    placeholder='例如 {"refreshToken":"...","clientSecret":"..."}'
                  />
                  <div class="field-hint">请求模板可通过 ${secret.refreshToken} 等变量引用。</div>
                </el-form-item>
              </div>
            </div>
          </el-form>
        </section>

        <!-- 2. 认证方式 -->
        <section v-show="activeSection === 'auth'" class="editor-section">
          <div class="section-heading">
            <div>
              <h3>认证方式</h3>
              <p>
                选择凭证如何获得。HTTP 登录可以配置多步认证链，例如“账密 → ticket → OTP → Cookie”。
              </p>
            </div>
          </div>

          <el-form :model="form" label-position="top" class="clean-form">
            <div class="field-card">
              <div class="field-label">更新方式</div>
              <div class="choice-grid auth-grid">
                <button
                  v-for="item in authModes"
                  :key="item.value"
                  type="button"
                  class="choice-card auth-choice"
                  :class="{ active: form.authMode === item.value }"
                  @click="form.authMode = item.value"
                >
                  <span class="choice-radio"></span>
                  <span>
                    <b>{{ item.title }}</b>
                    <small>{{ item.desc }}</small>
                  </span>
                </button>
              </div>
            </div>

            <div v-if="showLoginConfig" class="field-card">
              <div class="field-card-head">
                <div>
                  <div class="field-label">登录账号</div>
                  <div class="field-hint">
                    账号信息只配置一次，登录接口和兜底登录接口共享这些变量。
                  </div>
                </div>
              </div>

              <div class="two-col">
                <el-form-item label="用户名">
                  <el-input
                    v-model="sensitive.username"
                    autocomplete="off"
                    placeholder="目标系统登录账号"
                  />
                </el-form-item>
                <el-form-item label="密码">
                  <el-input
                    v-model="sensitive.password"
                    type="password"
                    show-password
                    autocomplete="new-password"
                    placeholder="目标系统登录密码"
                  />
                </el-form-item>
              </div>

              <div class="two-col">
                <el-form-item label="OTP 类型">
                  <el-select v-model="form.authConfig.otpType" style="width: 100%">
                    <el-option
                      v-for="item in otpTypes"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="form.authConfig.otpType === 'totp'" label="TOTP 密钥">
                  <el-input
                    v-model="sensitive.otpSecret"
                    type="password"
                    show-password
                    autocomplete="new-password"
                    placeholder="Base32，例如 JBSWY3DPEHPK3PXP"
                  />
                </el-form-item>
              </div>

              <div class="variable-hint">
                <span>可在请求模板中使用</span>
                <code>${secret.username}</code>
                <code>${secret.password}</code>
                <code>${secret.otp}</code>
              </div>
            </div>

            <div v-if="isHttpMode" class="flow-intro">
              <div class="flow-intro-icon">↳</div>
              <div>
                <b>{{
                  form.authMode === 'http_refresh' ? '刷新优先，登录兜底' : 'HTTP 认证流程'
                }}</b>
                <p>
                  {{
                    form.authMode === 'http_refresh'
                      ? '刷新失败时会执行登录配置；登录成功后可重新获取并重试刷新。'
                      : '单接口模式适合简单登录，多步模式适合 OTP、ticket、二次验证等有状态认证。'
                  }}
                </p>
              </div>
            </div>
          </el-form>
        </section>

        <!-- 3. 获取 / 刷新 -->
        <section v-show="activeSection === 'request'" class="editor-section">
          <div class="section-heading">
            <div>
              <h3>获取 / 刷新</h3>
              <p>把“请求 → 成功判断 → 输出”放在同一个认证单元里，减少来回查找。</p>
            </div>
          </div>

          <template v-if="requestEditors.length">
            <div v-for="editor in requestEditors" :key="editor.kind" class="request-card">
              <div class="request-card-head">
                <div class="request-title">
                  <span class="request-status-dot"></span>
                  <div>
                    <b>{{ editor.label }}</b>
                    <small>{{
                      editor.kind === 'login' ? '获取新的登录凭证' : '使用当前凭证续期'
                    }}</small>
                  </div>
                </div>
                <el-tag v-if="chainEnabled[editor.kind]" type="success" size="small"
                  >多步认证链</el-tag
                >
                <el-tag v-else type="info" size="small">单接口</el-tag>
              </div>

              <template v-if="editor.label === '兜底登录接口'">
                <div class="fallback-note">
                  兜底登录与主登录共用上方账号、OTP 配置，不需要重复填写；兜底登录同样支持多步认证链（与
                  HTTP 登录共用同一份多步链配置），刷新失败时按链式流程重新登录。
                </div>
              </template>

              <div class="chain-switch-row">
                <div>
                  <b>使用多步认证链</b>
                  <span>适用于“账密登录 → ticket → OTP → Cookie”等流程</span>
                </div>
                <el-switch v-model="chainEnabled[editor.kind]" />
              </div>

              <CredentialStepsEditor
                v-show="chainEnabled[editor.kind]"
                :ref="(element) => setStepsEditorRef(editor.kind, element)"
                v-model:enabled="chainEnabled[editor.kind]"
                :kind-label="editor.kind === 'login' ? '登录' : '刷新'"
              />

              <div v-if="chainEnabled[editor.kind] && form.credentialId" class="flow-test-row">
                <el-button
                  type="primary"
                  plain
                  :loading="flowTesting"
                  @click="testAuthFlow(editor.kind)"
                >
                  测试{{ editor.kind === 'login' ? '登录' : '刷新' }}流程
                </el-button>
                <el-input
                  v-if="['sms', 'email', 'manual'].includes(form.authConfig.otpType)"
                  v-model="flowTestOtpCode"
                  placeholder="本次测试验证码"
                  style="width: 220px"
                />
              </div>

              <div v-show="!chainEnabled[editor.kind]" class="single-request">
                <div class="request-tabs">
                  <button
                    type="button"
                    :class="{ active: requestTabs[editor.kind] === 'request' }"
                    @click="setRequestTab(editor.kind, 'request')"
                  >
                    请求
                  </button>
                  <button
                    type="button"
                    :class="{ active: requestTabs[editor.kind] === 'assertions' }"
                    @click="setRequestTab(editor.kind, 'assertions')"
                  >
                    成功判断 <em>{{ editor.request.assertions.length }}</em>
                  </button>
                  <button
                    type="button"
                    :class="{ active: requestTabs[editor.kind] === 'mappings' }"
                    @click="setRequestTab(editor.kind, 'mappings')"
                  >
                    响应提取 <em>{{ editor.request.mappings.length }}</em>
                  </button>
                </div>

                <div v-show="requestTabs[editor.kind] === 'request'" class="request-panel">
                  <div class="two-col request-top">
                    <el-form-item label="请求方法">
                      <el-select v-model="editor.request.method" style="width: 100%">
                        <el-option v-for="method in requestMethods" :key="method" :value="method" />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="接口地址" required>
                      <div class="url-editor">
                        <el-input
                          v-model="editor.request.url"
                          :placeholder="
                            editor.kind === 'login'
                              ? 'https://example.com/api/login'
                              : 'https://example.com/api/refresh'
                          "
                        />
                        <el-button
                          v-if="editor.kind === 'login'"
                          plain
                          @click="restoreLoginBodyTemplate"
                          >恢复模板</el-button
                        >
                      </div>
                    </el-form-item>
                  </div>

                  <div class="template-block">
                    <div class="template-label">请求 Header</div>
                    <div class="template-editor">
                      <el-input
                        :ref="
                          (element) => setTemplateInputRef(`${editor.kind}:headersText`, element)
                        "
                        v-model="editor.request.headersText"
                        type="textarea"
                        :rows="3"
                        placeholder='JSON，例如 {"Content-Type":"application/json"}'
                      />
                      <el-dropdown
                        trigger="click"
                        @command="
                          (variable) =>
                            insertTemplateVariable(`${editor.kind}:headersText`, variable)
                        "
                      >
                        <el-button plain>插入变量</el-button>
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item
                              v-for="variable in templateVariables"
                              :key="variable.value"
                              :command="variable.value"
                            >
                              <code>{{ variable.value }}</code
                              >（{{ variable.label }}）
                            </el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </div>
                  </div>

                  <div class="template-block">
                    <div class="template-label">查询参数</div>
                    <div class="template-editor">
                      <el-input
                        :ref="(element) => setTemplateInputRef(`${editor.kind}:queryText`, element)"
                        v-model="editor.request.queryText"
                        type="textarea"
                        :rows="3"
                        placeholder='JSON，例如 {"tenant":"prod"}'
                      />
                      <el-dropdown
                        trigger="click"
                        @command="
                          (variable) => insertTemplateVariable(`${editor.kind}:queryText`, variable)
                        "
                      >
                        <el-button plain>插入变量</el-button>
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item
                              v-for="variable in templateVariables"
                              :key="variable.value"
                              :command="variable.value"
                            >
                              <code>{{ variable.value }}</code
                              >（{{ variable.label }}）
                            </el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </div>
                  </div>

                  <div class="template-block">
                    <div class="template-label">JSON 请求体</div>
                    <div class="template-editor">
                      <el-input
                        :ref="(element) => setTemplateInputRef(`${editor.kind}:bodyText`, element)"
                        v-model="editor.request.bodyText"
                        type="textarea"
                        :rows="5"
                        :placeholder="editor.bodyPlaceholder"
                      />
                      <el-dropdown
                        trigger="click"
                        @command="
                          (variable) => insertTemplateVariable(`${editor.kind}:bodyText`, variable)
                        "
                      >
                        <el-button plain>插入变量</el-button>
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item
                              v-for="variable in templateVariables"
                              :key="variable.value"
                              :command="variable.value"
                            >
                              <code>{{ variable.value }}</code
                              >（{{ variable.label }}）
                            </el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </div>
                  </div>

                  <div class="template-block">
                    <div class="template-label">表单请求体</div>
                    <div class="template-editor">
                      <el-input
                        :ref="(element) => setTemplateInputRef(`${editor.kind}:dataText`, element)"
                        v-model="editor.request.dataText"
                        type="textarea"
                        :rows="4"
                        placeholder='仅 application/x-www-form-urlencoded 使用，例如 {"username":"${secret.username}"}'
                      />
                      <el-dropdown
                        trigger="click"
                        @command="
                          (variable) => insertTemplateVariable(`${editor.kind}:dataText`, variable)
                        "
                      >
                        <el-button plain>插入变量</el-button>
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item
                              v-for="variable in templateVariables"
                              :key="variable.value"
                              :command="variable.value"
                            >
                              <code>{{ variable.value }}</code
                              >（{{ variable.label }}）
                            </el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </div>
                  </div>
                </div>

                <div v-show="requestTabs[editor.kind] === 'assertions'" class="request-panel">
                  <div class="panel-tip">
                    HTTP 状态码为 2xx 后，所有配置的断言必须通过，才会提取并写回凭证。
                  </div>
                  <div
                    v-for="(item, index) in editor.request.assertions"
                    :key="`assertion-${index}`"
                    class="assertion-card-row"
                  >
                    <el-input
                      v-model="item.source"
                      placeholder="来源，如 json:code、status、cookie:SESSION"
                    />
                    <el-select v-model="item.operator" placeholder="操作符">
                      <el-option
                        v-for="operator in assertionOperators"
                        :key="operator.value"
                        :label="operator.label"
                        :value="operator.value"
                      />
                    </el-select>
                    <el-input
                      v-model="item.expectedText"
                      :disabled="['exists', 'not_empty'].includes(item.operator)"
                      placeholder='期望值，例如 "success"、true'
                    />
                    <el-input v-model="item.message" placeholder="失败提示（可选）" />
                    <el-button
                      :icon="Delete"
                      text
                      type="danger"
                      @click="editor.request.assertions.splice(index, 1)"
                      >删除</el-button
                    >
                  </div>
                  <el-button
                    :icon="Plus"
                    plain
                    @click="editor.request.assertions.push(emptyAssertion())"
                    >添加成功断言</el-button
                  >
                </div>

                <div v-show="requestTabs[editor.kind] === 'mappings'" class="request-panel">
                  <div class="panel-tip">
                    只配置需要更新的字段。未配置字段保留旧值；优先使用结构化 Cookie 单项更新。
                  </div>
                  <div
                    v-for="(item, index) in editor.request.mappings"
                    :key="index"
                    class="mapping-card-row"
                  >
                    <div>
                      <el-input
                        v-model="item.target"
                        placeholder="凭证字段，如 token / header.cookie.SESSION / cookies.SESSION"
                      />
                      <el-tag
                        v-if="item.target.trim() === 'header.cookie'"
                        type="danger"
                        size="small"
                        >覆盖整串 Cookie</el-tag
                      >
                    </div>
                    <el-input
                      v-model="item.source"
                      placeholder="来源，如 json:data.accessToken / cookie:SESSION / cookies"
                    />
                    <el-button
                      :icon="Delete"
                      text
                      type="danger"
                      @click="editor.request.mappings.splice(index, 1)"
                      >删除</el-button
                    >
                  </div>
                  <el-button
                    :icon="Plus"
                    plain
                    @click="editor.request.mappings.push({ target: '', source: '' })"
                    >添加提取规则</el-button
                  >
                </div>

                <div class="request-advanced">
                  <button
                    type="button"
                    @click="
                      requestAdvancedVisible[editor.kind] = !requestAdvancedVisible[editor.kind]
                    "
                  >
                    <span>变量与 Cookie 高级说明</span>
                    <span>{{ requestAdvancedVisible[editor.kind] ? '收起' : '展开' }}</span>
                  </button>
                  <div v-show="requestAdvancedVisible[editor.kind]" class="request-advanced-body">
                    <p>
                      凭证变量：<code>${secret.username}</code>、<code>${secret.password}</code>、<code>${secret.otp}</code>、<code>${secret.token}</code>、<code>${secret.cookie}</code>。
                    </p>
                    <p>
                      多条 Set-Cookie 可使用 <code>cookie:名称</code> 或
                      <code>header:set-cookie[n]</code> 提取；<code>header.cookie</code> 会覆盖整个
                      Cookie Header，属于高风险写法。
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <div v-else class="empty-request">
            <div class="empty-request-icon">✓</div>
            <b>当前认证方式不需要 HTTP 请求</b>
            <p>浏览器人工登录、浏览器刷新和手工录入在生命周期区域统一管理。</p>
          </div>
        </section>

        <!-- 4. 生命周期 -->
        <section v-show="activeSection === 'lifecycle'" class="editor-section">
          <div class="section-heading">
            <div>
              <h3>生命周期</h3>
              <p>定义凭证多久维护一次、谁可以同时使用，以及允许投影到哪些目标。</p>
            </div>
          </div>

          <el-form :model="form" label-position="top" class="clean-form">
            <div class="summary-card">
              <div class="summary-label">当前生命周期策略</div>
              <div class="summary-title">{{ lifecycleStrategy.label }}</div>
              <div class="summary-desc">{{ lifecycleStrategy.desc }}</div>
            </div>

            <div class="field-card">
              <div class="two-col">
                <el-form-item label="自动维护登录状态">
                  <div class="switch-line">
                    <el-switch v-model="form.autoRefreshEnabled" :disabled="!supportsAutoRefresh" />
                    <span>{{
                      supportsAutoRefresh ? '按周期执行认证流程' : '当前更新方式不支持自动维护'
                    }}</span>
                  </div>
                </el-form-item>
                <el-form-item v-if="form.autoRefreshEnabled" label="维护间隔">
                  <div class="number-line">
                    <el-input-number v-model="form.refreshIntervalSec" :min="60" />
                    <span>秒</span>
                  </div>
                </el-form-item>
              </div>
            </div>

            <div class="field-card">
              <div class="two-col">
                <el-form-item label="并发策略">
                  <el-select v-model="form.sharingMode" style="width: 100%">
                    <el-option
                      v-for="item in sharingModes"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="到期时间">
                  <el-date-picker
                    v-model="form.expireTime"
                    type="datetime"
                    placeholder="留空表示不设置"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    style="width: 100%"
                  />
                </el-form-item>
              </div>
              <el-form-item label="允许域名">
                <el-input
                  v-model="targetHostsText"
                  placeholder="多个域名用英文逗号分隔，例如 *.example.com, api.example.com"
                />
              </el-form-item>
            </div>

            <div class="advanced-card">
              <button
                type="button"
                class="advanced-head"
                @click="advancedVisible.lifecycle = !advancedVisible.lifecycle"
              >
                <span>
                  <b>其他设置</b>
                  <small>启用状态与备注</small>
                </span>
                <span class="advanced-toggle">{{
                  advancedVisible.lifecycle ? '收起' : '展开'
                }}</span>
              </button>
              <div v-show="advancedVisible.lifecycle" class="advanced-body">
                <el-form-item label="启用">
                  <el-switch v-model="form.enabled" />
                </el-form-item>
                <el-form-item label="备注">
                  <el-input
                    v-model="form.remark"
                    type="textarea"
                    :rows="3"
                    placeholder="记录凭证用途、账号范围或维护注意事项"
                  />
                </el-form-item>
              </div>
            </div>
          </el-form>
        </section>
      </div>

      <div class="editor-footer">
        <div class="footer-left">
          <el-tag
            v-if="form.authMode === 'http_login' && chainEnabled.login"
            type="success"
            size="small"
            >登录链已启用</el-tag
          >
          <el-tag
            v-if="form.authMode === 'http_refresh' && chainEnabled.refresh"
            type="success"
            size="small"
            >刷新链已启用</el-tag
          >
          <span class="footer-summary">{{ credentialResultSummary }}</span>
        </div>
        <div class="footer-actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button
            v-if="
              form.credentialId &&
              isHttpMode &&
              ((form.authMode === 'http_login' && chainEnabled.login) ||
                (form.authMode === 'http_refresh' && chainEnabled.refresh))
            "
            plain
            :loading="flowTesting"
            @click="testAuthFlow(form.authMode === 'http_login' ? 'login' : 'refresh')"
            >测试认证流程</el-button
          >
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </div>
      </div>

      <!-- 流程测试结果 -->
      <el-dialog v-model="flowTestVisible" title="认证流程测试结果" width="680px" append-to-body>
        <template v-if="flowTestResult">
          <el-alert type="success" :closable="false" show-icon :title="flowTestResult.message" />
          <div class="test-timeline">
            <div v-for="row in flowTestResult.steps || []" :key="row.index" class="test-step">
              <span class="test-step-no">{{ row.index }}</span>
              <div class="test-step-main">
                <b>{{ row.name }}</b>
                <span v-if="row.skipped">已跳过（{{ row.skipReason }}）</span>
                <span v-else>HTTP {{ row.status }} · {{ row.elapsedMs }}ms</span>
                <small v-if="row.outputs && row.outputs.length"
                  >{{ row.persistOutputs ? '写回' : '输出' }}：{{ row.outputs.join('、') }}</small
                >
              </div>
            </div>
          </div>
          <div
            v-if="flowTestResult.updatedFields && flowTestResult.updatedFields.length"
            class="test-fields"
          >
            本次将更新：{{ flowTestResult.updatedFields.join('、') }}（测试不会实际写回凭证）
          </div>
        </template>
        <template #footer>
          <el-button @click="flowTestVisible = false">关闭</el-button>
        </template>
      </el-dialog>
    </div>
  </el-dialog>
</template>

<script setup>
  import { Delete, Plus } from '@element-plus/icons-vue';
  import {
    addCredential,
    getCredentialSecret,
    testCredentialAuthFlow,
    updateCredential,
  } from '@/api/system/credential';
  import CredentialStepsEditor from './CredentialStepsEditor.vue';

  const emit = defineEmits(['saved']);
  const { proxy } = getCurrentInstance();
  const visible = ref(false);
  const saving = ref(false);
  const storageStateText = ref('');
  const advancedSecretText = ref('');
  const targetHostsText = ref('');
  const advancedPanels = ref([]);
  const additionalAuthLoaded = ref(false);
  const preservedSecretKeys = ref(new Set());
  /* 编辑打开时已保存 secret 的字段快照：输入框被清空的字段会在保存时显式传空串，由后端从旧密文中删除。 */
  const savedSecretKeys = ref(new Set());
  const requestTemplateInputRefs = {};
  const sensitive = reactive({
    cookie: '',
    headerName: '',
    headerValue: '',
    valuePrefix: 'Bearer ',
    token: '',
    username: '',
    password: '',
    otpSecret: '',
  });
  const requestMethods = ['GET', 'POST', 'PUT', 'PATCH'];
  const credentialTypes = [
    { value: 'browser_storage', label: '浏览器状态' },
    { value: 'http_cookie', label: 'HTTP Cookie' },
    { value: 'http_token', label: 'HTTP Token' },
    { value: 'http_api_key', label: 'API Key' },
    { value: 'http_header', label: 'HTTP Header' },
  ];
  const authModes = [
    {
      value: 'manual',
      label: '手工录入，不自动更新',
      title: '手工录入',
      desc: '固定 Token / API Key，不自动更新',
    },
    {
      value: 'http_login',
      label: 'HTTP 登录重新获取',
      title: 'HTTP 自动登录',
      desc: '调用登录接口获取凭证，支持多步认证链与 TOTP',
    },
    {
      value: 'http_refresh',
      label: 'HTTP 刷新（可配兜底登录）',
      title: 'HTTP 刷新',
      desc: '用现有 Cookie/Header 调接口续期，可配兜底登录',
    },
    {
      value: 'browser_login',
      label: '浏览器人工登录',
      title: '浏览器人工登录',
      desc: 'Agent 打开页面人工登录后回写状态',
    },
    {
      value: 'browser_refresh',
      label: '浏览器刷新',
      title: '浏览器刷新',
      desc: 'Agent 自动刷新浏览器状态',
    },
  ];
  const otpTypes = [
    { value: 'none', label: '不需要' },
    { value: 'totp', label: 'TOTP 自动生成' },
    { value: 'sms', label: '短信验证码（需人工/外部服务）' },
    { value: 'email', label: '邮箱验证码（需人工/外部服务）' },
    { value: 'manual', label: '人工确认' },
  ];
  const sharingModes = [
    { value: 'shared_read', label: '共享读取' },
    { value: 'exclusive_refresh', label: '刷新时独占' },
    { value: 'exclusive_use', label: '使用期间独占' },
  ];
  const assertionOperators = [
    { value: 'equals', label: '等于' },
    { value: 'not_equals', label: '不等于' },
    { value: 'exists', label: '存在' },
    { value: 'not_empty', label: '非空' },
    { value: 'contains', label: '包含' },
    { value: 'in', label: '属于' },
  ];
  const additionalHeaders = reactive([]);
  const additionalCookies = reactive([]);
  const emptyAssertion = () => ({ source: '', operator: 'equals', expectedText: '', message: '' });
  const emptyRequest = () => ({
    url: '',
    method: 'POST',
    headersText: '{}',
    queryText: '{}',
    bodyText: '{}',
    dataText: '{}',
    mappings: [],
    assertions: [],
  });
  const loginRequest = reactive(emptyRequest());
  const refreshRequest = reactive(emptyRequest());
  /* 多步认证链：按接口段（login/refresh）独立开关；开启后由步骤编辑器替代单接口配置。 */
  const chainEnabled = reactive({ login: false, refresh: false });
  const stepsEditorRefs = {};
  const flowTesting = ref(false);
  const flowTestOtpCode = ref('');
  const flowTestVisible = ref(false);
  const flowTestResult = ref(null);

  // UI-only state：不改变后端数据结构，仅控制新的分区/标签交互。
  const activeSection = ref('basic');
  const requestTabs = reactive({ login: 'request', refresh: 'request' });
  const advancedVisible = reactive({ basic: false, lifecycle: false });
  const requestAdvancedVisible = reactive({ login: false, refresh: false });

  function setSection(section) {
    activeSection.value = section;
  }

  function setRequestTab(kind, tab) {
    requestTabs[kind] = tab;
  }

  function resetUiState() {
    activeSection.value = 'basic';
    requestTabs.login = 'request';
    requestTabs.refresh = 'request';
    requestAdvancedVisible.login = false;
    requestAdvancedVisible.refresh = false;
    advancedVisible.basic = false;
    advancedVisible.lifecycle = false;
  }

  function setStepsEditorRef(kind, element) {
    if (element) stepsEditorRefs[kind] = element;
    else delete stepsEditorRefs[kind];
  }

  /** 测试多步认证链：真实执行各步骤并展示逐步明细，测试过程不写回凭证。 */
  async function testAuthFlow(kind) {
    try {
      flowTesting.value = true;
      const response = await testCredentialAuthFlow(form.credentialId, {
        flowType: kind,
        otpCode: flowTestOtpCode.value || null,
      });
      flowTestResult.value = response?.data || null;
      flowTestVisible.value = true;
    } catch (error) {
      proxy.$modal.msgError(error?.message || '认证流程测试失败');
    } finally {
      flowTesting.value = false;
    }
  }
  const emptyForm = () => ({
    credentialId: '',
    revision: 0,
    credentialName: '',
    credentialType: 'http_cookie',
    authMode: 'manual',
    enabled: true,
    autoRefreshEnabled: false,
    refreshIntervalSec: 0,
    sharingMode: 'shared_read',
    expireTime: '',
    authConfig: { otpType: 'none', targetHostPatterns: [] },
    remark: '',
  });
  const form = reactive(emptyForm());
  const isHttpMode = computed(() => ['http_login', 'http_refresh'].includes(form.authMode));
  const supportsAutoRefresh = computed(() =>
    ['http_login', 'http_refresh'].includes(form.authMode)
  );
  /* 生命周期策略：由"获取方式 + 是否自动维护"共同决定，向用户解释当前组合的实际行为。 */
  const lifecycleStrategy = computed(() => {
    if (!supportsAutoRefresh.value)
      return {
        label: '人工维护',
        desc: '凭证由人工录入或浏览器人工登录获取，平台不自动更新，请注意凭证有效期。',
      };
    if (!form.autoRefreshEnabled)
      return {
        label: '仅手工获取',
        desc: '可在编辑保存或手工刷新时更新凭证；未开启自动维护时到期后业务将无法使用。',
      };
    if (form.authMode === 'http_login')
      return {
        label: '定时重新认证',
        desc: `每 ${form.refreshIntervalSec || 0} 秒重新执行登录流程（含多步认证链），适合无刷新接口的系统。`,
      };
    return {
      label: '刷新优先，登录兜底',
      desc: `每 ${form.refreshIntervalSec || 0} 秒先执行刷新${
        chainEnabled.refresh ? '链' : ''
      }，失败后自动执行登录${chainEnabled.login ? '链' : ''}再重试刷新。`,
    };
  });
  /* 凭证结果摘要：告诉用户认证成功后系统实际保存哪些内容。 */
  const credentialResultSummary = computed(() => {
    if (form.authMode === 'http_login') {
      if (chainEnabled.login) return '按认证流程中开启"写回凭证"的步骤输出保存（见流程预览）';
      const targets = loginRequest.mappings
        .filter((item) => item.target.trim())
        .map((item) => item.target.trim());
      return targets.length ? targets.join('、') : '未配置响应提取规则（登录后不会更新凭证内容）';
    }
    if (form.authMode === 'http_refresh') {
      if (chainEnabled.refresh) return '按刷新流程中开启"写回凭证"的步骤输出保存（见流程预览）';
      const targets = refreshRequest.mappings
        .filter((item) => item.target.trim())
        .map((item) => item.target.trim());
      return targets.length ? targets.join('、') : '未配置响应提取规则（刷新后不会更新凭证内容）';
    }
    if (form.credentialType === 'browser_storage')
      return '浏览器 storageState（由 Agent 登录后回写）';
    return '凭证内容区手工录入的字段';
  });
  const showLoginConfig = computed(() => form.authMode === 'http_login');
  // HTTP 登录和 HTTP 刷新都复用同一组请求编辑器；http_refresh 会同时展示刷新接口和兜底登录接口。
  const requestEditors = computed(() => {
    if (form.authMode === 'http_login') {
      return [
        {
          kind: 'login',
          label: '登录接口',
          bodyPlaceholder: '{"username":"${secret.username}","password":"${secret.password}"}',
          request: loginRequest,
        },
      ];
    }
    if (form.authMode === 'http_refresh') {
      return [
        {
          kind: 'refresh',
          label: '刷新接口',
          bodyPlaceholder: '{}，刷新时当前 Cookie/Header 会自动携带',
          request: refreshRequest,
        },
        {
          kind: 'login',
          label: '兜底登录接口',
          bodyPlaceholder: '{"username":"${secret.username}","password":"${secret.password}"}',
          request: loginRequest,
        },
      ];
    }
    return [];
  });
  const hasCookieHeaderPrimary = computed(
    () =>
      ['http_header', 'http_api_key'].includes(form.credentialType) &&
      sensitive.headerName.trim().toLowerCase() === 'cookie'
  );
  const templateVariables = [
    { value: '${secret.username}', label: '登录用户名' },
    { value: '${secret.password}', label: '登录密码' },
    { value: '${secret.otp}', label: 'OTP 验证码' },
    { value: '${secret.token}', label: '当前 Token' },
    { value: '${secret.cookie}', label: '当前完整 Cookie' },
    { value: '${secret.headerValue}', label: '主 Header 值', advanced: true },
  ];
  const templateVariableNamePattern = /^[A-Za-z_][A-Za-z0-9_]*$/;

  watch([() => form.authMode, () => form.authConfig.otpType], ([mode]) => {
    if (mode === 'http_login' || mode === 'http_refresh') ensureLoginRequestDefaults();
    if (!supportsAutoRefresh.value) form.autoRefreshEnabled = false;
  });
  function jsonText(value) {
    return JSON.stringify(value || {}, null, 2);
  }
  function jsonValueText(value) {
    return value === undefined ? '' : JSON.stringify(value);
  }
  function restoreRedacted(value) {
    if (Array.isArray(value)) return value.map(restoreRedacted);
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        item === '******' ? `\${secret.${key}}` : restoreRedacted(item),
      ])
    );
  }
  function mappingRows(mapping) {
    return Object.entries(mapping || {}).map(([target, source]) => ({ target, source }));
  }
  function assertionRows(assertions) {
    return (assertions || []).map((item) => ({
      source: item?.source || '',
      operator: item?.operator || 'equals',
      expectedText: jsonValueText(item?.expected),
      message: item?.message || '',
    }));
  }
  function replaceRows(target, rows) {
    target.splice(0, target.length, ...rows);
  }
  function keyValueRows(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
      ? Object.entries(value).map(([name, item]) => ({ name, value: String(item) }))
      : [];
  }
  function resetRequest(target, config, prefix) {
    const template = restoreRedacted(config?.[`${prefix}RequestTemplate`] || {});
    Object.assign(target, emptyRequest(), {
      url: config?.[`${prefix}Url`] || '',
      method: config?.[`${prefix}Method`] || config?.requestMethod || 'POST',
      headersText: jsonText(template.headers),
      queryText: jsonText(template.query || template.params),
      bodyText: jsonText(template.body),
      dataText: jsonText(template.data),
      mappings: mappingRows(config?.[`${prefix}ResponseMapping`] || config?.responseMapping),
      assertions: assertionRows(config?.[`${prefix}SuccessAssertions`]),
    });
  }

  /** 将解密后的 secret 字典回填到表单敏感字段，编辑时用于回显。 */
  function populateFromSecret(secret) {
    if (!secret || typeof secret !== 'object' || !Object.keys(secret).length) return;
    savedSecretKeys.value = new Set(Object.keys(secret));
    if (secret.cookie != null) sensitive.cookie = String(secret.cookie);
    if (secret.headerName != null) sensitive.headerName = String(secret.headerName);
    if (secret.headerValue != null) sensitive.headerValue = String(secret.headerValue);
    if (secret.valuePrefix != null) sensitive.valuePrefix = String(secret.valuePrefix);
    if (secret.token != null) sensitive.token = String(secret.token);
    if (secret.username != null) sensitive.username = String(secret.username);
    if (secret.password != null) sensitive.password = String(secret.password);
    if (secret.otpSecret != null) sensitive.otpSecret = String(secret.otpSecret);
    replaceRows(additionalHeaders, keyValueRows(secret.headers));
    replaceRows(additionalCookies, keyValueRows(secret.cookies));
    preservedSecretKeys.value = new Set(Object.keys(secret));
    additionalAuthLoaded.value = true;
    if (secret.storageState != null)
      storageStateText.value = JSON.stringify(secret.storageState, null, 2);
    const standardKeys = [
      'cookie',
      'cookies',
      'headerName',
      'headerValue',
      'valuePrefix',
      'token',
      'username',
      'password',
      'otpSecret',
      'storageState',
      'headers',
    ];
    const extra = {};
    for (const [key, value] of Object.entries(secret)) {
      if (!standardKeys.includes(key)) extra[key] = value;
    }
    if (Object.keys(extra).length) advancedSecretText.value = JSON.stringify(extra, null, 2);
    if (additionalHeaders.length || additionalCookies.length || advancedSecretText.value.trim())
      advancedPanels.value = ['additional-auth'];
  }
  function ensureLoginRequestDefaults() {
    /* 默认登录模板仅在新增凭证时自动注入；编辑已有凭证时尊重用户已保存的内容，避免清空后被再次填回。 */
    if (!form.credentialId && loginRequest.bodyText.trim() === '{}') {
      loginRequest.bodyText = jsonText({
        username: '${secret.username}',
        password: '${secret.password}',
      });
    }
    if (form.authConfig.otpType !== 'totp') return;
    try {
      const body = parseObject(loginRequest.bodyText, 'JSON 请求体');
      if (!Object.values(body).includes('${secret.otp}'))
        loginRequest.bodyText = jsonText({ ...body, otp: '${secret.otp}' });
    } catch (_) {
      /* 用户正在编辑 JSON 时不覆盖输入。 */
    }
  }
  /** 将登录接口的 JSON 请求体恢复为默认的账号密码占位模板，由用户显式触发。 */
  function restoreLoginBodyTemplate() {
    loginRequest.bodyText = jsonText({
      username: '${secret.username}',
      password: '${secret.password}',
    });
  }
  function open(row) {
    resetUiState();
    Object.assign(form, emptyForm(), row || {}, {
      authConfig: { ...emptyForm().authConfig, ...(row?.authConfig || {}) },
    });
    Object.keys(sensitive).forEach((key) => {
      sensitive[key] = key === 'valuePrefix' ? 'Bearer ' : '';
    });
    storageStateText.value = '';
    advancedSecretText.value = '';
    additionalAuthLoaded.value = false;
    preservedSecretKeys.value = new Set();
    savedSecretKeys.value = new Set();
    advancedPanels.value = [];
    replaceRows(additionalHeaders, []);
    replaceRows(additionalCookies, []);
    targetHostsText.value = (form.authConfig.targetHostPatterns || []).join(', ');
    resetRequest(loginRequest, form.authConfig, 'login');
    resetRequest(refreshRequest, form.authConfig, 'refresh');
    /* 多步认证链状态与步骤内容回填：已保存过步骤才默认开启，避免误导单接口用户。
       loginSteps 在 http_login 模式是主登录链，在 http_refresh 模式是兜底登录链，两种模式都回填。 */
    const savedLoginSteps = form.authConfig.loginSteps || [];
    const savedRefreshSteps = form.authConfig.refreshSteps || [];
    chainEnabled.login =
      ['http_login', 'http_refresh'].includes(form.authMode) && savedLoginSteps.length > 0;
    chainEnabled.refresh = form.authMode === 'http_refresh' && savedRefreshSteps.length > 0;
    flowTestOtpCode.value = '';
    flowTestResult.value = null;
    if (form.authMode === 'http_login' || form.authMode === 'http_refresh')
      ensureLoginRequestDefaults();
    nextTick(() => {
      if (stepsEditorRefs.login)
        stepsEditorRefs.login.loadSteps(chainEnabled.login ? savedLoginSteps : []);
      if (stepsEditorRefs.refresh)
        stepsEditorRefs.refresh.loadSteps(chainEnabled.refresh ? savedRefreshSteps : []);
    });
    visible.value = true;
    /* 编辑时从后端获取解密后的凭证明文并回填到表单，敏感字段默认 mask 可通过眼睛图标查看 */
    if (row?.credentialId) {
      getCredentialSecret(row.credentialId)
        .then((response) => {
          const secret = response?.data;
          if (secret) populateFromSecret(secret);
        })
        .catch(() => {
          /* 无权限或解密失败时保持字段为空，用户可手动填写 */
        });
    }
  }
  function parseObject(text, label) {
    const value = JSON.parse(text || '{}');
    if (!value || Array.isArray(value) || typeof value !== 'object')
      throw new Error(`${label}必须是 JSON 对象`);
    return value;
  }
  function setTemplateInputRef(field, component) {
    if (component) requestTemplateInputRefs[field] = component;
    else delete requestTemplateInputRefs[field];
  }
  function resolveRequestEditor(field) {
    const [kind, requestField] = String(field || '').split(':');
    return { request: kind === 'login' ? loginRequest : refreshRequest, requestField };
  }
  function isJsonStringPosition(source, position) {
    let insideString = false;
    let escaped = false;
    for (const character of source.slice(0, position)) {
      if (escaped) {
        escaped = false;
        continue;
      }
      if (insideString && character === '\\') {
        escaped = true;
        continue;
      }
      if (character === '"') insideString = !insideString;
    }
    return insideString;
  }
  function insertTemplateVariable(field, variable) {
    const { request, requestField } = resolveRequestEditor(field);
    const component = requestTemplateInputRefs[field];
    const input = component?.$el?.querySelector('textarea');
    const source = String(request[requestField] || '');
    const start = input?.selectionStart ?? source.length;
    const end = input?.selectionEnd ?? source.length;
    const insertion = isJsonStringPosition(source, start) ? variable : `"${variable}"`;
    request[requestField] = `${source.slice(0, start)}${insertion}${source.slice(end)}`;
    const cursor = start + insertion.length;
    nextTick(() => {
      const current = requestTemplateInputRefs[field]?.$el?.querySelector('textarea');
      if (!current) return;
      current.focus();
      current.setSelectionRange(cursor, cursor);
    });
  }
  function buildRequest(request) {
    return {
      headers: parseObject(request.headersText, '请求 Header'),
      query: parseObject(request.queryText, '查询参数'),
      body: parseObject(request.bodyText, 'JSON 请求体'),
      data: parseObject(request.dataText, '表单请求体'),
    };
  }
  function availableTemplateVariableKeys(secret) {
    const keys = new Set([...preservedSecretKeys.value, ...Object.keys(secret || {})]);
    const headerValueExists = keys.has('headerValue') || keys.has('header_value');
    if (hasCookieHeaderPrimary.value && headerValueExists) keys.add('cookie');
    if (form.authConfig.otpType !== 'none' && (keys.has('otpSecret') || keys.has('otp_secret')))
      keys.add('otp');
    return keys;
  }
  function collectTemplateVariables(value, location, variables) {
    if (typeof value === 'string') {
      const expressions = [...value.matchAll(/\$\{secret\.([^}]*)\}/g)];
      if ((value.match(/\$\{secret\./g) || []).length !== expressions.length)
        throw new Error(`${location}存在未闭合的凭证变量`);
      for (const expression of expressions)
        variables.push({ expression: expression[0], name: expression[1], location });
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((item, index) =>
        collectTemplateVariables(item, `${location}[${index}]`, variables)
      );
      return;
    }
    if (value && typeof value === 'object')
      Object.entries(value).forEach(([key, item]) =>
        collectTemplateVariables(item, `${location}.${key}`, variables)
      );
  }
  function validateRequestTemplateVariables(authConfig, secret) {
    const availableKeys = availableTemplateVariableKeys(secret);
    const templates = [
      ['登录请求模板', authConfig.loginRequestTemplate],
      ['刷新请求模板', authConfig.refreshRequestTemplate],
    ];
    for (const [label, template] of templates) {
      const variables = [];
      collectTemplateVariables(template, label, variables);
      for (const variable of variables) {
        if (!templateVariableNamePattern.test(variable.name))
          throw new Error(
            `${variable.location}中的变量 ${variable.expression} 格式错误；仅支持 ${'${secret.字段名}'}，字段名只能包含字母、数字和下划线`
          );
        if (!availableKeys.has(variable.name))
          throw new Error(
            `${variable.location}引用了 ${variable.expression}，但当前凭证没有填写对应的 ${variable.name} 字段；请在登录账号区域填写，或点击"恢复默认模板"后补填账号，不需要账号时请清空该模板中的账号密码变量`
          );
      }
    }
  }
  function validateResponseMappingTargets(authConfig) {
    if (!hasCookieHeaderPrimary.value) return;
    for (const [label, mapping] of [
      ['登录响应提取规则', authConfig.loginResponseMapping],
      ['刷新响应提取规则', authConfig.refreshResponseMapping],
    ]) {
      const target = Object.keys(mapping || {}).find(
        (item) => item === 'cookies' || item.startsWith('cookies.')
      );
      if (target)
        throw new Error(
          `${label}不能使用 ${target}：主 Header 名称为 Cookie 时，请使用 header.cookie 或 header.cookie.<名称> 写回 Cookie`
        );
    }
  }
  function buildMapping(request) {
    return Object.fromEntries(
      request.mappings
        .filter((item) => item.target.trim() && item.source.trim())
        .map((item) => [item.target.trim(), item.source.trim()])
    );
  }
  function buildKeyValue(rows, label, caseInsensitive = false) {
    const result = {};
    const seen = new Set();
    for (const item of rows) {
      const name = item.name.trim();
      const value = item.value;
      if (!name && !value) continue;
      if (!name) throw new Error(`${label}名称不能为空`);
      const uniqueName = caseInsensitive ? name.toLowerCase() : name;
      if (seen.has(uniqueName)) throw new Error(`${label}名称不能重复：${name}`);
      seen.add(uniqueName);
      result[name] = value;
    }
    return result;
  }
  function buildAssertions(request) {
    return request.assertions
      .filter((item) => item.source.trim() || item.expectedText.trim() || item.message.trim())
      .map((item, index) => {
        const source = item.source.trim();
        if (!source) throw new Error(`第 ${index + 1} 条成功断言未填写来源`);
        const requiresExpected = !['exists', 'not_empty'].includes(item.operator);
        if (requiresExpected && !item.expectedText.trim())
          throw new Error(`第 ${index + 1} 条成功断言未填写期望值`);
        let expected = null;
        if (requiresExpected) {
          try {
            expected = JSON.parse(item.expectedText);
          } catch (_) {
            throw new Error(`第 ${index + 1} 条成功断言的期望值必须是合法 JSON`);
          }
        }
        return { source, operator: item.operator, expected, message: item.message.trim() };
      });
  }
  function buildSecret() {
    const secret = {};
    if (form.credentialType === 'http_cookie' && sensitive.cookie.trim())
      secret.cookie = sensitive.cookie.trim();
    else if (form.credentialType === 'http_cookie' && savedSecretKeys.value.has('cookie'))
      secret.cookie = '';
    if (['http_header', 'http_api_key'].includes(form.credentialType)) {
      if (sensitive.headerName.trim()) secret.headerName = sensitive.headerName.trim();
      else if (savedSecretKeys.value.has('headerName')) secret.headerName = '';
      if (sensitive.headerValue) secret.headerValue = sensitive.headerValue;
      else if (savedSecretKeys.value.has('headerValue')) secret.headerValue = '';
    }
    if (form.credentialType === 'http_token') {
      if (sensitive.headerName.trim()) secret.headerName = sensitive.headerName.trim();
      else if (savedSecretKeys.value.has('headerName')) secret.headerName = '';
      if (sensitive.valuePrefix) secret.valuePrefix = sensitive.valuePrefix;
      else if (savedSecretKeys.value.has('valuePrefix')) secret.valuePrefix = '';
      if (sensitive.token) secret.token = sensitive.token;
      else if (savedSecretKeys.value.has('token')) secret.token = '';
    }
    if (storageStateText.value.trim())
      secret.storageState = parseObject(storageStateText.value, 'storageState');
    else if (savedSecretKeys.value.has('storageState')) secret.storageState = '';
    const headers = buildKeyValue(additionalHeaders, '附加 Header', true);
    const cookies = buildKeyValue(additionalCookies, '附加 Cookie');
    const hasCookieHeader =
      hasCookieHeaderPrimary.value ||
      Object.keys(headers).some((name) => name.toLowerCase() === 'cookie');
    if (hasCookieHeader && Object.keys(cookies).length)
      throw new Error('Cookie Header 与结构化附加 Cookie 不能同时配置');
    if (Object.keys(headers).length || additionalAuthLoaded.value) secret.headers = headers;
    if (Object.keys(cookies).length || additionalAuthLoaded.value) secret.cookies = cookies;
    if (advancedSecretText.value.trim()) {
      const advanced = parseObject(advancedSecretText.value, '其他敏感字段');
      if ('headers' in advanced || 'cookies' in advanced)
        throw new Error('额外 Header 和 Cookie 请使用附加认证信息区域配置');
      Object.assign(secret, advanced);
    }
    for (const key of ['username', 'password', 'otpSecret']) {
      if (sensitive[key]) secret[key] = sensitive[key];
      else if (savedSecretKeys.value.has(key)) secret[key] = '';
    }
    return secret;
  }
  async function save() {
    try {
      if (!form.credentialName.trim()) return proxy.$modal.msgError('请填写凭证名称');
      if (form.autoRefreshEnabled && !supportsAutoRefresh.value)
        return proxy.$modal.msgError('当前更新方式不支持自动刷新');
      const secret = buildSecret();
      /* 多步链开启时段的单接口配置整体置空，避免两套配置同时存在产生歧义；关闭后恢复编辑器原值。 */
      /* 多步链开启时段的单接口配置整体置空，避免两套配置同时存在产生歧义；关闭后恢复编辑器原值。
         loginSteps 在 http_refresh 模式下是兜底登录链，因此 loginChainActive 覆盖两种 HTTP 模式。 */
      const loginChainActive =
        ['http_login', 'http_refresh'].includes(form.authMode) && chainEnabled.login;
      const refreshChainActive = form.authMode === 'http_refresh' && chainEnabled.refresh;
      const authConfig = {
        ...form.authConfig,
        targetHostPatterns: targetHostsText.value
          .split(',')
          .map((v) => v.trim())
          .filter(Boolean),
        loginUrl: loginChainActive ? '' : loginRequest.url,
        refreshUrl: refreshChainActive ? '' : refreshRequest.url,
        loginMethod: loginChainActive ? 'POST' : loginRequest.method,
        refreshMethod: refreshChainActive ? 'POST' : refreshRequest.method,
        loginRequestTemplate: loginChainActive ? {} : buildRequest(loginRequest),
        refreshRequestTemplate: refreshChainActive ? {} : buildRequest(refreshRequest),
        loginResponseMapping: loginChainActive ? {} : buildMapping(loginRequest),
        refreshResponseMapping: refreshChainActive ? {} : buildMapping(refreshRequest),
        loginSuccessAssertions: loginChainActive ? [] : buildAssertions(loginRequest),
        refreshSuccessAssertions: refreshChainActive ? [] : buildAssertions(refreshRequest),
        loginSteps:
          loginChainActive && stepsEditorRefs.login ? stepsEditorRefs.login.buildSteps() : [],
        refreshSteps:
          refreshChainActive && stepsEditorRefs.refresh ? stepsEditorRefs.refresh.buildSteps() : [],
      };
      validateRequestTemplateVariables(authConfig, secret);
      validateResponseMappingTargets(authConfig);
      const data = { ...form, expireTime: form.expireTime || null, secret, authConfig };
      saving.value = true;
      const request = form.credentialId
        ? updateCredential(form.credentialId, { ...data, expectedRevision: form.revision })
        : addCredential(data);
      await request;
      proxy.$modal.msgSuccess('保存成功');
      visible.value = false;
      emit('saved');
    } catch (error) {
      proxy.$modal.msgError(error?.message || '配置格式错误');
    } finally {
      saving.value = false;
    }
  }

  defineExpose({ open });
</script>

<style scoped>
  .credential-editor {
    --editor-border: var(--el-border-color-light);
    --editor-muted: var(--el-text-color-secondary);
    --editor-soft: var(--el-fill-color-light);
    --editor-radius: 10px;
    display: flex;
    flex-direction: column;
    height: min(86vh, 820px);
    min-height: 620px;
    background: var(--el-bg-color);
    color: var(--el-text-color-primary);
    overflow: hidden;
  }

  .editor-head {
    flex: 0 0 auto;
    display: flex;
    justify-content: space-between;
    gap: 24px;
    padding: 20px 28px 16px;
    border-bottom: 1px solid var(--editor-border);
  }
  .editor-kicker {
    font-size: 12px;
    color: var(--el-color-primary);
    font-weight: 600;
    letter-spacing: 0.04em;
  }
  .editor-title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
    font-size: 22px;
    font-weight: 650;
  }
  .editor-subtitle,
  .editor-head-meta {
    color: var(--editor-muted);
    font-size: 13px;
  }
  .editor-subtitle {
    margin-top: 6px;
  }
  .editor-head-meta {
    padding-top: 4px;
    white-space: nowrap;
  }

  .editor-steps {
    flex: 0 0 auto;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    padding: 12px 28px;
    gap: 8px;
    background: var(--editor-soft);
    border-bottom: 1px solid var(--editor-border);
  }
  .editor-step {
    appearance: none;
    border: 1px solid transparent;
    background: transparent;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    text-align: left;
    cursor: pointer;
    color: inherit;
  }
  .editor-step:hover {
    background: var(--el-bg-color);
  }
  .editor-step.active {
    background: var(--el-bg-color);
    border-color: var(--el-color-primary-light-5);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  }
  .editor-step-no {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--el-fill-color);
    color: var(--editor-muted);
    font-size: 12px;
    font-weight: 700;
  }
  .editor-step.active .editor-step-no {
    background: var(--el-color-primary);
    color: #fff;
  }
  .editor-step-copy {
    min-width: 0;
  }
  .editor-step-copy b,
  .editor-step-copy small {
    display: block;
  }
  .editor-step-copy b {
    font-size: 13px;
  }
  .editor-step-copy small {
    margin-top: 2px;
    color: var(--editor-muted);
    font-size: 11px;
    white-space: nowrap;
  }

  .editor-body {
    flex: 1 1 auto;
    min-height: 0;
    overflow: auto;
    padding: 24px 28px 32px;
    background: var(--el-bg-color-page);
  }
  .editor-section {
    max-width: 1100px;
    margin: 0 auto;
  }
  .section-heading {
    display: flex;
    justify-content: space-between;
    margin-bottom: 18px;
  }
  .section-heading h3 {
    margin: 0;
    font-size: 18px;
  }
  .section-heading p {
    margin: 5px 0 0;
    color: var(--editor-muted);
    font-size: 13px;
  }

  .clean-form :deep(.el-form-item) {
    margin-bottom: 16px;
  }
  .field-card,
  .request-card,
  .advanced-card,
  .summary-card {
    background: var(--el-bg-color);
    border: 1px solid var(--editor-border);
    border-radius: var(--editor-radius);
    padding: 18px 20px;
    margin-bottom: 14px;
  }
  .field-card-head,
  .request-card-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 16px;
  }
  .field-label {
    font-size: 14px;
    font-weight: 650;
    margin-bottom: 4px;
  }
  .field-hint,
  .request-card-head small {
    color: var(--editor-muted);
    font-size: 12px;
    line-height: 1.5;
  }

  .choice-grid {
    display: grid;
    gap: 10px;
  }
  .credential-type-grid {
    grid-template-columns: repeat(5, 1fr);
  }
  .auth-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .choice-card {
    appearance: none;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    text-align: left;
    padding: 13px;
    border: 1px solid var(--editor-border);
    background: var(--el-bg-color);
    border-radius: 9px;
    cursor: pointer;
    color: inherit;
    transition: 0.15s ease;
  }
  .choice-card:hover {
    border-color: var(--el-color-primary-light-5);
  }
  .choice-card.active {
    border-color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
  }
  .choice-radio {
    flex: 0 0 auto;
    width: 14px;
    height: 14px;
    border: 1px solid var(--el-border-color);
    border-radius: 50%;
    margin-top: 2px;
    position: relative;
  }
  .choice-card.active .choice-radio {
    border-color: var(--el-color-primary);
    box-shadow:
      inset 0 0 0 3px var(--el-bg-color),
      0 0 0 1px var(--el-color-primary);
    background: var(--el-color-primary);
  }
  .choice-card b,
  .choice-card small {
    display: block;
  }
  .choice-card b {
    font-size: 13px;
  }
  .choice-card small {
    margin-top: 4px;
    color: var(--editor-muted);
    font-size: 11px;
    line-height: 1.45;
  }

  .two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }
  .three-col {
    display: grid;
    grid-template-columns: 1fr 1fr 1.2fr;
    gap: 16px;
  }
  .variable-hint,
  .flow-intro,
  .fallback-note,
  .panel-tip {
    border-radius: 8px;
    background: var(--el-fill-color-light);
    color: var(--editor-muted);
    font-size: 12px;
    line-height: 1.6;
    padding: 10px 12px;
  }
  .variable-hint {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  code {
    font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    background: var(--el-fill-color-darker);
    border-radius: 4px;
    padding: 2px 5px;
    font-size: 11px;
  }

  .advanced-card {
    padding: 0;
    overflow: hidden;
  }
  .advanced-head {
    width: 100%;
    border: 0;
    background: transparent;
    display: flex;
    justify-content: space-between;
    align-items: center;
    text-align: left;
    padding: 15px 18px;
    cursor: pointer;
    color: inherit;
  }
  .advanced-head b,
  .advanced-head small {
    display: block;
  }
  .advanced-head small {
    margin-top: 3px;
    color: var(--editor-muted);
    font-size: 11px;
  }
  .advanced-toggle {
    color: var(--el-color-primary);
    font-size: 12px;
  }
  .advanced-body {
    border-top: 1px solid var(--editor-border);
    padding: 18px 20px 4px;
  }

  .kv-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .kv-row {
    display: grid;
    grid-template-columns: 1fr 1.4fr auto;
    gap: 8px;
    align-items: center;
  }

  .flow-intro {
    display: flex;
    gap: 12px;
    margin-bottom: 14px;
  }
  .flow-intro-icon {
    width: 26px;
    height: 26px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    background: var(--el-color-primary-light-8);
    color: var(--el-color-primary);
    font-weight: 700;
  }
  .flow-intro p {
    margin: 3px 0 0;
  }

  .request-card {
    padding: 0;
    overflow: hidden;
  }
  .request-card-head {
    margin: 0;
    padding: 16px 18px;
    border-bottom: 1px solid var(--editor-border);
  }
  .request-title {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .request-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--el-color-success);
  }
  .request-title b,
  .request-title small {
    display: block;
  }
  .request-title small {
    margin-top: 2px;
    color: var(--editor-muted);
    font-size: 11px;
  }
  .chain-switch-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 18px;
    background: var(--el-fill-color-light);
    border-bottom: 1px solid var(--editor-border);
  }
  .chain-switch-row b,
  .chain-switch-row span {
    display: block;
  }
  .chain-switch-row span {
    color: var(--editor-muted);
    font-size: 11px;
    margin-top: 2px;
  }
  .flow-test-row {
    display: flex;
    gap: 8px;
    padding: 12px 18px;
    border-bottom: 1px solid var(--editor-border);
  }
  .single-request {
    padding: 0 18px 18px;
  }
  .request-tabs {
    display: flex;
    gap: 2px;
    margin: 0 -18px 18px;
    padding: 0 18px;
    border-bottom: 1px solid var(--editor-border);
  }
  .request-tabs button {
    border: 0;
    background: transparent;
    padding: 11px 12px;
    color: var(--editor-muted);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    font-size: 13px;
  }
  .request-tabs button.active {
    color: var(--el-color-primary);
    border-bottom-color: var(--el-color-primary);
    font-weight: 600;
  }
  .request-tabs em {
    font-style: normal;
    font-size: 10px;
    background: var(--el-fill-color);
    border-radius: 10px;
    padding: 1px 5px;
    margin-left: 4px;
  }
  .request-panel {
    min-height: 100px;
  }
  .request-top {
    margin-top: 4px;
  }
  .url-editor,
  .template-editor {
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }
  .url-editor > .el-input,
  .template-editor > .el-input {
    flex: 1;
    min-width: 0;
  }
  .template-block {
    margin-top: 14px;
  }
  .template-label {
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 6px;
  }
  .assertion-card-row,
  .mapping-card-row {
    display: grid;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
  }
  .assertion-card-row {
    grid-template-columns: 1.2fr 110px 1fr 1fr auto;
  }
  .mapping-card-row {
    grid-template-columns: 1fr 1.3fr auto;
  }
  .mapping-card-row > div {
    min-width: 0;
  }
  .mapping-card-row .el-tag {
    margin-top: 4px;
  }
  .request-advanced {
    margin-top: 18px;
    border-top: 1px dashed var(--editor-border);
  }
  .request-advanced > button {
    width: 100%;
    display: flex;
    justify-content: space-between;
    padding: 10px 0;
    border: 0;
    background: transparent;
    color: var(--editor-muted);
    cursor: pointer;
    font-size: 12px;
  }
  .request-advanced-body {
    padding: 0 0 4px;
    color: var(--editor-muted);
    font-size: 12px;
    line-height: 1.7;
  }
  .request-advanced-body p {
    margin: 3px 0;
  }

  .empty-request {
    text-align: center;
    padding: 70px 20px;
    color: var(--editor-muted);
  }
  .empty-request-icon {
    width: 44px;
    height: 44px;
    margin: 0 auto 12px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--el-color-success-light-9);
    color: var(--el-color-success);
    font-weight: 700;
  }
  .empty-request p {
    font-size: 12px;
  }

  .summary-card {
    background: var(--el-color-primary-light-9);
    border-color: var(--el-color-primary-light-7);
  }
  .summary-label {
    color: var(--editor-muted);
    font-size: 12px;
  }
  .summary-title {
    font-size: 17px;
    font-weight: 650;
    margin-top: 5px;
  }
  .summary-desc {
    color: var(--editor-muted);
    font-size: 12px;
    line-height: 1.6;
    margin-top: 4px;
  }
  .switch-line,
  .number-line {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 32px;
  }
  .switch-line span,
  .number-line span {
    color: var(--editor-muted);
    font-size: 12px;
  }

  .editor-footer {
    flex: 0 0 auto;
    min-height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 10px 28px;
    border-top: 1px solid var(--editor-border);
    background: var(--el-bg-color);
  }
  .footer-left {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .footer-summary {
    color: var(--editor-muted);
    font-size: 11px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 500px;
  }
  .footer-actions {
    display: flex;
    gap: 8px;
    flex: 0 0 auto;
  }

  .test-timeline {
    margin-top: 16px;
  }
  .test-step {
    display: flex;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid var(--editor-border);
  }
  .test-step-no {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: var(--el-fill-color);
    display: grid;
    place-items: center;
    font-size: 11px;
    font-weight: 700;
    flex: 0 0 auto;
  }
  .test-step-main b,
  .test-step-main span,
  .test-step-main small {
    display: block;
  }
  .test-step-main span {
    color: var(--editor-muted);
    font-size: 12px;
    margin-top: 3px;
  }
  .test-step-main small {
    color: var(--el-color-primary);
    font-size: 11px;
    margin-top: 3px;
  }
  .test-fields {
    margin-top: 12px;
    color: var(--editor-muted);
    font-size: 12px;
  }

  .compact-alert {
    margin-bottom: 14px;
  }

  @media (max-width: 1000px) {
    .credential-type-grid {
      grid-template-columns: repeat(3, 1fr);
    }
    .auth-grid {
      grid-template-columns: repeat(2, 1fr);
    }
    .assertion-card-row {
      grid-template-columns: 1fr 120px 1fr;
    }
    .mapping-card-row {
      grid-template-columns: 1fr 1fr;
    }
  }
  @media (max-width: 760px) {
    .editor-head,
    .editor-body,
    .editor-footer {
      padding-left: 16px;
      padding-right: 16px;
    }
    .editor-steps {
      padding: 8px 16px;
      grid-template-columns: 1fr 1fr;
    }
    .editor-step-copy small {
      display: none;
    }
    .credential-type-grid,
    .auth-grid,
    .two-col,
    .three-col {
      grid-template-columns: 1fr;
    }
    .kv-row,
    .assertion-card-row,
    .mapping-card-row {
      grid-template-columns: 1fr;
    }
    .editor-footer {
      align-items: flex-end;
      flex-direction: column;
    }
    .footer-left {
      width: 100%;
    }
  }

  :deep(.credential-dialog .el-dialog__header) {
    display: none;
  }
  :deep(.credential-dialog .el-dialog__body) {
    padding: 0;
  }
  :deep(.credential-dialog .el-dialog__footer) {
    display: none;
  }
</style>
