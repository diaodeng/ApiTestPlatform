<template>
  <el-dialog v-model="visible" :title="form.credentialId ? '编辑凭证' : '新增凭证'" width="880px" append-to-body destroy-on-close>
    <el-form :model="form" label-width="126px">
      <el-divider content-position="left">基本信息</el-divider>
      <el-form-item label="凭证名称" required><el-input v-model="form.credentialName" /></el-form-item>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item>
            <template #label>凭证类型<PromptButton width="520"><div class="credential-help"><div class="credential-help-title">凭证类型说明</div><table class="credential-help-table"><thead><tr><th>类型</th><th>用途</th><th>填写内容</th></tr></thead><tbody><tr><td>浏览器状态</td><td>Web 用例 Playwright 自动化</td><td>录制/执行后的 storageState JSON</td></tr><tr><td>HTTP Cookie</td><td>带 Cookie 的 HTTP 请求</td><td>Cookie 字符串，如 SESSION=xxx; tenant=prod</td></tr><tr><td>HTTP Token</td><td>JWT/Bearer Token 等</td><td>Header 名 + 值前缀 + Token 值</td></tr><tr><td>API Key</td><td>固定密钥</td><td>Header 名 + 密钥值</td></tr><tr><td>HTTP Header</td><td>自定义请求头</td><td>Header 名 + 自定义值</td></tr></tbody></table><div class="credential-help-note">一个凭证只能选择一种类型，对应一组认证信息。</div></div></PromptButton></template>
            <el-select v-model="form.credentialType" style="width:100%"><el-option v-for="item in credentialTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item>
            <template #label>更新方式<PromptButton width="560"><div class="credential-help"><div class="credential-help-title">更新方式说明</div><table class="credential-help-table"><thead><tr><th>方式</th><th>适用场景</th><th>自动刷新</th></tr></thead><tbody><tr><td>手工录入</td><td>长期有效的 API Key / 静态 Token</td><td>不支持</td></tr><tr><td>HTTP 登录</td><td>需要账号密码登录获取凭证</td><td>支持（TOTP 可自动）</td></tr><tr><td>HTTP 刷新</td><td>用现有 Cookie/Header 调刷新接口续期；可配置兜底登录接口，刷新失败后自动登录并重试</td><td>支持</td></tr><tr><td>浏览器人工登录</td><td>人工在浏览器中登录</td><td>不支持</td></tr><tr><td>浏览器刷新</td><td>浏览器自动刷新状态</td><td>视实现而定</td></tr></tbody></table><div class="credential-help-note">手工录入初始值后想自动续期，请选择"HTTP 刷新"并按需配置刷新接口和兜底登录接口。</div></div></PromptButton></template>
            <el-select v-model="form.authMode" style="width:100%"><el-option v-for="item in authModes" :key="item.value" :label="item.label" :value="item.value" /></el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-divider content-position="left">凭证内容</el-divider>
      <el-alert type="info" :closable="false" show-icon class="section-alert">
        <template #title>编辑时会从服务端获取已保存凭证并回填，敏感字段默认掩码显示，点击右侧眼睛图标可查看明文。将已保存的字段清空后保存会从凭证中删除该字段。</template>
      </el-alert>
      <template v-if="form.credentialType === 'http_cookie'">
        <el-form-item>
          <template #label>Cookie<PromptButton width="460"><div class="credential-help"><div class="credential-help-title">Cookie 填写说明</div><p>完整的 Cookie 字符串，多个键值对用 <b>分号+空格</b> 分隔。</p><div class="credential-help-code">SESSION=abc123; tenant=prod; locale=zh-CN</div><p>系统会将其解析为多个键值对，并在请求时自动携带。</p></div></PromptButton></template>
          <el-input v-model="sensitive.cookie" type="textarea" :rows="3" placeholder="例如 SESSION=xxx; tenant=prod" />
        </el-form-item>
      </template>
      <template v-else-if="form.credentialType === 'http_header' || form.credentialType === 'http_api_key'">
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item>
              <template #label>Header 名称<PromptButton placement="top" width="380"><div class="credential-help"><div class="credential-help-title">Header 名称说明</div><p>请求头的键名，最终发送为 <b>{名称}: {值}</b>。</p><div class="credential-help-code">X-API-Key / Authorization / X-Auth-Token</div></div></PromptButton></template>
              <el-input v-model="sensitive.headerName" placeholder="例如 X-API-Key" />
            </el-form-item>
          </el-col>
          <el-col :span="14">
            <el-form-item>
              <template #label>Header 值<PromptButton placement="top" width="380"><div class="credential-help"><div class="credential-help-title">Header 值说明</div><p>请求头的值，即密钥或令牌内容。一个凭证只对应 <b>一组</b> Header 键值对。</p><div class="credential-help-code">sk-xxxx / eyJhbGci...</div></div></PromptButton></template>
              <el-input v-model="sensitive.headerValue" type="password" show-password autocomplete="new-password" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>
      <template v-else-if="form.credentialType === 'http_token'">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item>
              <template #label>Header 名称<PromptButton placement="top" width="380"><div class="credential-help"><div class="credential-help-title">Header 名称说明</div><p>认证请求头的键名，通常是 <b>Authorization</b>。</p><div class="credential-help-code">Authorization</div></div></PromptButton></template>
              <el-input v-model="sensitive.headerName" placeholder="Authorization" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <template #label>值前缀<PromptButton placement="top" width="400"><div class="credential-help"><div class="credential-help-title">值前缀说明</div><p>Token 类型前缀，系统自动拼接为 <b>{值前缀}{Token}</b>。</p><div class="credential-help-code">Bearer （注意末尾空格）</div><p>最终请求头示例：<b>Authorization: Bearer eyJhbG...</b></p></div></PromptButton></template>
              <el-input v-model="sensitive.valuePrefix" placeholder="Bearer " />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item>
              <template #label>Token<PromptButton placement="top" width="380"><div class="credential-help"><div class="credential-help-title">Token 说明</div><p>实际的令牌值，<b>不含前缀</b>。系统会与值前缀拼接后放入请求头。</p><div class="credential-help-code">eyJhbGciOiJIUzI1NiIs...</div></div></PromptButton></template>
              <el-input v-model="sensitive.token" type="password" show-password autocomplete="new-password" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>
      <el-form-item v-else label="storageState"><el-input v-model="storageStateText" type="textarea" :rows="5" placeholder='Playwright storageState，例如 {"cookies":[],"origins":[]}' /></el-form-item>
      <el-collapse v-if="form.credentialType !== 'browser_storage'" v-model="advancedPanels" class="credential-collapse">
        <el-collapse-item name="additional-auth" title="附加认证信息（可选）">
          <el-alert type="info" :closable="false" show-icon class="section-alert" title="主凭证保持上方类型对应的单一字段。这里仅用于补充 CSRF、租户等额外 Header 或额外 Cookie；不需要时无需展开配置。" />
          <el-alert v-if="hasCookieHeaderPrimary" type="warning" :closable="false" show-icon class="section-alert" title="主 Header 已使用 Cookie，不能新增或编辑结构化附加 Cookie。若下方存在历史附加 Cookie，请点击删除图标清理后再保存。" />
          <el-form-item label="附加 Header">
            <div class="key-value-list">
              <div v-for="(item, index) in additionalHeaders" :key="`header-${index}`" class="key-value-row">
                <el-input v-model="item.name" placeholder="名称，例如 X-CSRF-Token" />
                <el-input v-model="item.value" type="password" show-password autocomplete="new-password" placeholder="值" />
                <el-button :icon="Delete" circle plain type="danger" title="删除附加 Header" @click="additionalHeaders.splice(index, 1)" />
              </div>
              <el-button :icon="Plus" plain @click="additionalHeaders.push({ name: '', value: '' })">添加 Header</el-button>
            </div>
          </el-form-item>
          <el-form-item label="附加 Cookie">
            <div class="key-value-list">
              <div v-for="(item, index) in additionalCookies" :key="`cookie-${index}`" class="key-value-row">
                <el-input v-model="item.name" placeholder="名称，例如 CSRF-TOKEN" :disabled="hasCookieHeaderPrimary" />
                <el-input v-model="item.value" type="password" show-password autocomplete="new-password" placeholder="值" :disabled="hasCookieHeaderPrimary" />
                <el-button :icon="Delete" circle plain type="danger" title="删除附加 Cookie" @click="additionalCookies.splice(index, 1)" />
              </div>
              <el-button :icon="Plus" plain :disabled="hasCookieHeaderPrimary" @click="additionalCookies.push({ name: '', value: '' })">添加 Cookie</el-button>
            </div>
          </el-form-item>
          <el-form-item>
            <template #label>其他敏感字段 JSON<PromptButton width="500"><div class="credential-help"><div class="credential-help-title">其他敏感字段说明</div><p>存放主体凭证之外的固定敏感值，同样会加密保存。</p><p>额外 Header 和 Cookie 请使用上方字段，不要重复写入 JSON。</p><p>常见用途：</p><ul><li>刷新令牌：<code>{"refreshToken": "xxx"}</code></li><li>其他密钥：<code>{"clientSecret": "xxx"}</code></li></ul><p>请求模板中可引用：<code>${secret.refreshToken}</code></p></div></PromptButton></template>
            <el-input v-model="advancedSecretText" type="textarea" :rows="3" placeholder='可选，例如 {"refreshToken":"...","clientSecret":"..."}；固定敏感值会加密保存' />
          </el-form-item>
        </el-collapse-item>
      </el-collapse>

      <template v-if="showLoginConfig">
        <el-divider content-position="left">登录账号</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item>
              <template #label>用户名<PromptButton placement="top" width="440"><div class="credential-help"><div class="credential-help-title">登录用户名说明</div><p>目标系统的登录账号，会被加密保存。</p><p>在请求模板中通过 <b>${secret.username}</b> 引用。</p><p>来源：由用户自行填写目标系统的登录账号。</p></div></PromptButton></template>
              <el-input v-model="sensitive.username" autocomplete="off" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item>
              <template #label>密码<PromptButton placement="top" width="440"><div class="credential-help"><div class="credential-help-title">登录密码说明</div><p>目标系统的登录密码，会被加密保存。</p><p>在请求模板中通过 <b>${secret.password}</b> 引用。</p><p>来源：由用户自行填写目标系统的登录密码。</p></div></PromptButton></template>
              <el-input v-model="sensitive.password" type="password" show-password autocomplete="new-password" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item>
              <template #label>OTP 类型<PromptButton placement="top" width="460"><div class="credential-help"><div class="credential-help-title">OTP（一次性密码）类型说明</div><table class="credential-help-table"><thead><tr><th>类型</th><th>说明</th><th>自动刷新可用</th></tr></thead><tbody><tr><td>不需要</td><td>登录不要求二次验证</td><td>是</td></tr><tr><td>TOTP 自动生成</td><td>基于时间的一次性密码，需填写 TOTP 密钥</td><td>是</td></tr><tr><td>短信验证码</td><td>需人工接收短信</td><td>否</td></tr><tr><td>邮箱验证码</td><td>需人工查收邮件</td><td>否</td></tr><tr><td>人工确认</td><td>需人工手动确认</td><td>否</td></tr></tbody></table><p>验证码通过 <b>${secret.otp}</b> 注入请求体。</p></div></PromptButton></template>
              <el-select v-model="form.authConfig.otpType" style="width:100%"><el-option v-for="item in otpTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="form.authConfig.otpType === 'totp'" :span="12">
            <el-form-item>
              <template #label>TOTP 密钥<PromptButton placement="top" width="440"><div class="credential-help"><div class="credential-help-title">TOTP 密钥说明</div><p>目标系统提供的 TOTP 共享密钥（通常是一串 Base32 编码的字符串）。系统会基于此密钥按标准 RFC 6238 算法自动生成 6 位验证码。</p><div class="credential-help-code">JBSWY3DPEHPK3PXP</div></div></PromptButton></template>
              <el-input v-model="sensitive.otpSecret" type="password" show-password autocomplete="new-password" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <template v-if="requestEditors.length">

        <el-alert v-if="form.authMode === 'http_refresh'" type="success" :closable="false" show-icon class="section-alert" title="HTTP 刷新模式下会同时配置两段请求：刷新接口和兜底登录接口。刷新失败后会先执行登录，再用登录后的新凭证重试刷新。" />
        <el-collapse class="credential-collapse">
            <el-collapse-item v-for="editor in requestEditors" :key="editor.kind" :title="editor.label">
            <template v-if="editor.label==='兜底登录接口'">
            <el-divider content-position="left">登录账号</el-divider>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item>
                  <template #label>用户名<PromptButton placement="top" width="440"><div class="credential-help"><div class="credential-help-title">登录用户名说明</div><p>目标系统的登录账号，会被加密保存。</p><p>在请求模板中通过 <b>${secret.username}</b> 引用。</p><p>来源：由用户自行填写目标系统的登录账号。</p></div></PromptButton></template>
                  <el-input v-model="sensitive.username" autocomplete="off" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item>
                  <template #label>密码<PromptButton placement="top" width="440"><div class="credential-help"><div class="credential-help-title">登录密码说明</div><p>目标系统的登录密码，会被加密保存。</p><p>在请求模板中通过 <b>${secret.password}</b> 引用。</p><p>来源：由用户自行填写目标系统的登录密码。</p></div></PromptButton></template>
                  <el-input v-model="sensitive.password" type="password" show-password autocomplete="new-password" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item>
                  <template #label>OTP 类型<PromptButton placement="top" width="460"><div class="credential-help"><div class="credential-help-title">OTP（一次性密码）类型说明</div><table class="credential-help-table"><thead><tr><th>类型</th><th>说明</th><th>自动刷新可用</th></tr></thead><tbody><tr><td>不需要</td><td>登录不要求二次验证</td><td>是</td></tr><tr><td>TOTP 自动生成</td><td>基于时间的一次性密码，需填写 TOTP 密钥</td><td>是</td></tr><tr><td>短信验证码</td><td>需人工接收短信</td><td>否</td></tr><tr><td>邮箱验证码</td><td>需人工查收邮件</td><td>否</td></tr><tr><td>人工确认</td><td>需人工手动确认</td><td>否</td></tr></tbody></table><p>验证码通过 <b>${secret.otp}</b> 注入请求体。</p></div></PromptButton></template>
                  <el-select v-model="form.authConfig.otpType" style="width:100%"><el-option v-for="item in otpTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select>
                </el-form-item>
              </el-col>
              <el-col v-if="form.authConfig.otpType === 'totp'" :span="12">
                <el-form-item>
                  <template #label>TOTP 密钥<PromptButton placement="top" width="440"><div class="credential-help"><div class="credential-help-title">TOTP 密钥说明</div><p>目标系统提供的 TOTP 共享密钥（通常是一串 Base32 编码的字符串）。系统会基于此密钥按标准 RFC 6238 算法自动生成 6 位验证码。</p><div class="credential-help-code">JBSWY3DPEHPK3PXP</div></div></PromptButton></template>
                  <el-input v-model="sensitive.otpSecret" type="password" show-password autocomplete="new-password" />
                </el-form-item>
              </el-col>
            </el-row>
            </template>
        <el-collapse class="credential-collapse">
            <el-collapse-item title="请求信息">
        <el-alert type="info" :closable="false" show-icon class="section-alert">
          <template #title>请求模板可引用已加密保存的 <code>${secret.变量名}</code>。使用各输入框右侧的“插入变量”时，光标在 JSON 字符串外会自动补全双引号；保存前会校验变量格式和可用性。<code>${secret.headerValue}</code> 为高级用法，直接读取 HTTP Header / API Key 的主 Header 值；通常请优先使用 <code>${secret.cookie}</code>、<code>${secret.token}</code> 等语义变量。</template>
        </el-alert>
        <el-row :gutter="16">
          <el-col :span="7"><el-form-item label="请求方法"><el-select v-model="editor.request.method" style="width:100%"><el-option v-for="method in requestMethods" :key="method" :value="method" /></el-select></el-form-item></el-col>
          <el-col :span="17">
            <el-form-item label="接口地址" required>
              <div class="url-editor">
                <el-input v-model="editor.request.url" :placeholder="editor.kind === 'login' ? 'https://example.com/api/login' : 'https://example.com/api/refresh'" />
                <el-button v-if="editor.kind === 'login'" plain title="将 JSON 请求体恢复为默认的账号密码模板" @click="restoreLoginBodyTemplate">恢复默认模板</el-button>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <template #label>请求 Header<PromptButton placement="top" width="440"><div class="credential-help"><div class="credential-help-title">请求 Header 说明</div><p>JSON 对象格式，额外的 HTTP 请求头。系统会自动携带当前凭证的 Cookie/Header，无需在此重复填写。</p><div class="credential-help-code">{"Content-Type":"application/json"}</div></div></PromptButton></template>
          <div class="template-editor">
            <el-input :ref="element => setTemplateInputRef(`${editor.kind}:headersText`, element)" v-model="editor.request.headersText" type="textarea" :rows="2" placeholder='JSON，例如 {"Content-Type":"application/json"}' />
            <el-dropdown trigger="click" @command="variable => insertTemplateVariable(`${editor.kind}:headersText`, variable)">
              <el-button plain>插入变量</el-button>
              <template #dropdown><el-dropdown-menu><el-dropdown-item v-for="variable in templateVariables" :key="variable.value" :command="variable.value" :divided="variable.advanced"><code>{{ variable.value }}</code>（{{ variable.label }}<template v-if="variable.advanced">，高级用法</template>）</el-dropdown-item></el-dropdown-menu></template>
            </el-dropdown>
          </div>
        </el-form-item>
        <el-form-item>
          <template #label>查询参数<PromptButton placement="top" width="400"><div class="credential-help"><div class="credential-help-title">查询参数说明</div><p>JSON 对象格式，URL 查询字符串参数。</p><div class="credential-help-code">{"tenant":"prod", "source":"api"}</div></div></PromptButton></template>
          <div class="template-editor">
            <el-input :ref="element => setTemplateInputRef(`${editor.kind}:queryText`, element)" v-model="editor.request.queryText" type="textarea" :rows="2" placeholder='JSON，例如 {"tenant":"prod"}' />
            <el-dropdown trigger="click" @command="variable => insertTemplateVariable(`${editor.kind}:queryText`, variable)">
              <el-button plain>插入变量</el-button>
              <template #dropdown><el-dropdown-menu><el-dropdown-item v-for="variable in templateVariables" :key="variable.value" :command="variable.value" :divided="variable.advanced"><code>{{ variable.value }}</code>（{{ variable.label }}<template v-if="variable.advanced">，高级用法</template>）</el-dropdown-item></el-dropdown-menu></template>
            </el-dropdown>
          </div>
        </el-form-item>
        <el-form-item>
          <template #label>JSON 请求体<PromptButton placement="top" width="520"><div class="credential-help"><div class="credential-help-title">JSON 请求体说明</div><p>JSON 对象格式，用于 <b>application/json</b> 类型的请求。可使用占位符引用加密字段：</p><table class="credential-help-table"><thead><tr><th>占位符</th><th>说明</th></tr></thead><tbody><tr><td><code>${secret.username}</code></td><td>登录用户名</td></tr><tr><td><code>${secret.password}</code></td><td>登录密码</td></tr><tr><td><code>${secret.otp}</code></td><td>OTP 验证码（自动生成或手工输入）</td></tr><tr><td><code>${secret.token}</code></td><td>当前存储的 Token 值</td></tr><tr><td><code>${secret.cookie}</code></td><td>当前完整 Cookie；主 Header 名称为 Cookie 时自动读取其 Header 值</td></tr><tr><td><code>${secret.headerValue}</code></td><td><b>高级用法</b>：直接读取 HTTP Header / API Key 的主 Header 值</td></tr></tbody></table><p>占位符变量来自凭证 secret 中的字段名，系统发送请求前会自动替换。</p></div></PromptButton></template>
          <div class="template-editor">
            <el-input :ref="element => setTemplateInputRef(`${editor.kind}:bodyText`, element)" v-model="editor.request.bodyText" type="textarea" :rows="4" :placeholder="editor.bodyPlaceholder" />
            <el-dropdown trigger="click" @command="variable => insertTemplateVariable(`${editor.kind}:bodyText`, variable)">
              <el-button plain>插入变量</el-button>
              <template #dropdown><el-dropdown-menu><el-dropdown-item v-for="variable in templateVariables" :key="variable.value" :command="variable.value" :divided="variable.advanced"><code>{{ variable.value }}</code>（{{ variable.label }}<template v-if="variable.advanced">，高级用法</template>）</el-dropdown-item></el-dropdown-menu></template>
            </el-dropdown>
          </div>
        </el-form-item>
        <el-form-item>
          <template #label>表单请求体<PromptButton placement="top" width="460"><div class="credential-help"><div class="credential-help-title">表单请求体说明</div><p>JSON 对象格式，用于 <b>application/x-www-form-urlencoded</b> 请求。支持与 JSON 请求体相同的占位符引用。</p><div class="credential-help-code">{"username":"${secret.username}","password":"${secret.password}"}</div></div></PromptButton></template>
          <div class="template-editor">
            <el-input :ref="element => setTemplateInputRef(`${editor.kind}:dataText`, element)" v-model="editor.request.dataText" type="textarea" :rows="3" placeholder='仅 application/x-www-form-urlencoded 使用，例如 {"username":"${secret.username}"}' />
            <el-dropdown trigger="click" @command="variable => insertTemplateVariable(`${editor.kind}:dataText`, variable)">
              <el-button plain>插入变量</el-button>
              <template #dropdown><el-dropdown-menu><el-dropdown-item v-for="variable in templateVariables" :key="variable.value" :command="variable.value" :divided="variable.advanced"><code>{{ variable.value }}</code>（{{ variable.label }}<template v-if="variable.advanced">，高级用法</template>）</el-dropdown-item></el-dropdown-menu></template>
            </el-dropdown>
          </div>
        </el-form-item>
        </el-collapse-item>
        </el-collapse>

        <el-collapse class="credential-collapse">
            <el-collapse-item name="assert" title="成功断言">
                <el-alert type="info" :closable="false" show-icon class="section-alert">
                <template #title>
                    HTTP 状态码为 2xx 后，所有已配置断言都必须通过，才会提取并写回凭证。未配置时仅按 HTTP 状态码和响应提取结果判断。
                    <PromptButton placement="top" width="560" :teleported="true"><div class="credential-help"><div class="credential-help-title">成功断言说明</div><p>断言用于判断接口业务是否真正成功，和响应提取规则分开配置。</p><table class="credential-help-table"><thead><tr><th>来源</th><th>示例</th></tr></thead><tbody><tr><td>HTTP 状态码</td><td><code>status</code></td></tr><tr><td>JSON 字段</td><td><code>json:code</code>、<code>json:data.success</code></td></tr><tr><td>响应头</td><td><code>header:X-Result</code></td></tr><tr><td>标准响应 Cookie</td><td><code>cookie:SESSION</code></td></tr></tbody></table><p>期望值必须是合法 JSON：字符串填写 <code>"0000"</code>，数字填写 <code>0</code>，布尔值填写 <code>true</code>，集合填写 <code>[200,201]</code>。</p><div class="credential-help-note">例如：来源 <code>json:code</code>、操作符 <code>等于</code>、期望值 <code>"0000"</code>。任一断言失败都会保留旧凭证。</div></div></PromptButton>
                </template>
                </el-alert>
                <div v-for="(item, index) in editor.request.assertions" :key="`assertion-${index}`" class="assertion-row">
                <el-input v-model="item.source" placeholder="来源，例如 json:code、status" />
                <el-select v-model="item.operator" placeholder="操作符"><el-option v-for="operator in assertionOperators" :key="operator.value" :label="operator.label" :value="operator.value" /></el-select>
                <el-input v-model="item.expectedText" :disabled="['exists', 'not_empty'].includes(item.operator)" placeholder='期望值，例如 "0000"、true、[200,201]' />
                <el-input v-model="item.message" placeholder="失败提示（可选）" />
                <el-button :icon="Delete" circle plain type="danger" title="删除成功断言" @click="editor.request.assertions.splice(index, 1)" />
                </div>
                <el-button :icon="Plus" plain @click="editor.request.assertions.push(emptyAssertion())">添加成功断言</el-button>
            </el-collapse-item>
        </el-collapse>

        <el-collapse class="credential-collapse">
            <el-collapse-item name="get_response" title="响应提取">
                <el-alert type="info" :closable="false" show-icon class="section-alert">
                <template #title>
                    把响应中的新值写回凭证字段。
                    <PromptButton placement="top" width="580" :teleported="true">
                    <div class="credential-help">
                        <div class="credential-help-title">响应提取规则详细说明</div>
                    <p><b>凭证字段</b>（左）：要写入的凭证位置。只有配置了规则的目标才会更新；可以配置多条规则，分别更新 Header、Token 和结构化 Cookie。</p>
                        <table class="credential-help-table">
                        <thead><tr><th>凭证字段</th><th>对应凭证类型</th><th>写入方式</th></tr></thead>
                        <tbody><tr><td>token</td><td>HTTP Token</td><td>直接替换 Token 值</td></tr><tr><td>header.cookie</td><td>HTTP Header（Header 名为 Cookie）</td><td>覆盖整个 Cookie Header，未包含的 Cookie 会丢失</td></tr><tr><td>header.cookie.UYBFEWAEE</td><td>HTTP Header（Header 名为 Cookie）</td><td>只替换该 Cookie；原 Header 没有该项时追加</td></tr><tr><td>cookies</td><td>HTTP Cookie / 其他敏感字段</td><td>覆盖整个结构化 Cookie 对象</td></tr><tr><td>cookies.SESSION</td><td>HTTP Cookie / 其他敏感字段</td><td>只更新结构化 Cookie 中的 SESSION，其他项保留</td></tr><tr><td>headerValue / headerName</td><td>API Key / HTTP Header</td><td>直接替换整个字段</td></tr></tbody>
                        </table>
                        <p style="margin-top:10px"><b>来源</b>（右）：从响应中提取值的路径，格式为 <b>类型:路径</b>：</p>
                        <table class="credential-help-table">
                        <thead><tr><th>格式</th><th>含义</th><th>示例</th></tr></thead>
                        <tbody><tr><td>json:路径</td><td>从 JSON 响应体提取</td><td>json:data.accessToken</td></tr><tr><td>header:名称</td><td>从单个响应头提取；header:set-cookie 读取唯一原始 Set-Cookie 值</td><td>header:X-Auth-Token</td></tr><tr><td>header:set-cookie[n]</td><td>从多条原始 Set-Cookie 中按序号选择一条，序号从 1 开始</td><td>header:set-cookie[1]</td></tr><tr><td>cookie:名称</td><td>从标准 Set-Cookie 中提取单个 Cookie 值</td><td>cookie:SESSION</td></tr><tr><td>cookies</td><td>提取全部标准 Set-Cookie 为对象</td><td>cookies</td></tr></tbody>
                        </table>
                        <p style="margin-top:10px"><b>Cookie 更新示例：</b></p>
                        <table class="credential-help-table">
                        <thead><tr><th>凭证字段</th><th>来源</th><th>行为</th></tr></thead>
                        <tbody><tr><td>header.cookie.UYBFEWAEE</td><td>header:set-cookie</td><td>适用于响应 <code>Set-Cookie: new_value</code>，将 new_value 写入 Cookie 内 UYBFEWAEE 项</td></tr><tr><td>header.cookie.SESSION</td><td>cookie:SESSION</td><td>适用于标准响应 <code>Set-Cookie: SESSION=new_value; Path=/</code></td></tr><tr><td>cookies</td><td>cookies</td><td>以响应中全部标准 Set-Cookie 覆盖现有结构化 Cookie 对象</td></tr><tr><td>cookies.SESSION</td><td>cookie:SESSION</td><td>仅更新结构化 Cookie 中的 SESSION</td></tr></tbody>
                        </table>
                        <div class="credential-help-note">
                        <p><b>关键约束：</b></p>
                        <ul>
                            <li><b>header.cookie</b> 和 <b>header.cookie.名称</b> 仅在 Header 名称为 Cookie 时有效，大小写不敏感</li>
                            <li><b>header.cookie</b> 会覆盖整串 Cookie Header，属于高风险操作；优先使用 <b>header.cookie.名称</b> 更新单项</li>
                            <li>响应含多条 Set-Cookie 时不能直接用 <b>header:set-cookie</b> 写入单个值；请使用 <b>header:set-cookie[1]</b> 这类序号规则明确选择一条，或用 <b>cookie:名称</b> 读取标准 Cookie</li>
                            <li><b>cookies ← cookies</b> 会覆盖整组结构化 Cookie；响应没有标准 Set-Cookie 时不会以空对象覆盖旧值</li>
                            <li>未配置规则的字段不会自动更新，包括响应中的 Set-Cookie</li>
                            <li>提取结果会与旧凭证合并，未提取的字段保留原值</li>
                        </ul>
                        </div>
                    </div>
                    </PromptButton>
                </template>
                </el-alert>
                <div v-for="(item, index) in editor.request.mappings" :key="index" class="mapping-row">
                <div class="mapping-target">
                    <el-input v-model="item.target" placeholder="凭证字段，例如 token、header.cookie.SESSION、cookies.SESSION" />
                    <el-tag v-if="item.target.trim() === 'header.cookie'" type="danger" size="small">高风险：覆盖整个 Cookie Header</el-tag>
                </div>
                <el-input v-model="item.source" placeholder="来源，例如 json:data.accessToken、header:X-Auth-Token、cookie:SESSION" />
                <el-button :icon="Delete" circle plain type="danger" title="删除映射" @click="editor.request.mappings.splice(index, 1)" />
                </div>
                <el-button :icon="Plus" plain @click="editor.request.mappings.push({ target: '', source: '' })">添加提取规则</el-button>
            </el-collapse-item>
        </el-collapse>
        </el-collapse-item>
        </el-collapse>
      </template>

      <el-collapse class="credential-collapse">
        <el-collapse-item name="status_fresh" title="刷新与状态">
            <el-form-item>
                <template #label>自动刷新<PromptButton placement="top" width="420"><div class="credential-help"><div class="credential-help-title">自动刷新说明</div><p>开启后定时任务会按间隔自动调用登录或刷新接口更新凭证。</p><p><b>仅"HTTP 登录"和"HTTP 刷新"支持自动刷新。</b></p><p>刷新间隔至少 60 秒。建议根据凭证有效期设置，如 Token 有效期 30 分钟则设 1500 秒。</p></div></PromptButton></template>
                <el-switch v-model="form.autoRefreshEnabled" :disabled="!supportsAutoRefresh" /><el-input-number v-if="form.autoRefreshEnabled" v-model="form.refreshIntervalSec" :min="60" class="ml8" /><span v-if="form.autoRefreshEnabled" class="ml8 unit-text">秒</span>
            </el-form-item>
            <el-form-item>
                <template #label>并发策略<PromptButton width="460"><div class="credential-help"><div class="credential-help-title">并发策略说明</div><table class="credential-help-table"><thead><tr><th>策略</th><th>说明</th></tr></thead><tbody><tr><td>共享读取</td><td>多个任务可同时使用凭证，互不影响</td></tr><tr><td>刷新时独占</td><td>刷新期间锁定凭证，其他任务等待</td></tr><tr><td>使用期间独占</td><td>使用和刷新期间均锁定凭证</td></tr></tbody></table><div class="credential-help-note">会使同账号会话失效的系统建议选择"刷新时独占"或"使用期间独占"。</div></div></PromptButton></template>
                <el-select v-model="form.sharingMode" style="width:100%"><el-option v-for="item in sharingModes" :key="item.value" :label="item.label" :value="item.value" /></el-select>
            </el-form-item>
            <el-form-item>
                <template #label>允许域名<PromptButton placement="top" width="420"><div class="credential-help"><div class="credential-help-title">允许域名说明</div><p>凭证允许被投影到的目标域名模式，多个用英文逗号分隔。</p><div class="credential-help-code">*.example.com, api.example.com, 192.168.*</div><p>支持通配符 <b>*</b>，留空表示不限制域名。</p></div></PromptButton></template>
                <el-input v-model="targetHostsText" placeholder="多个域名用英文逗号分隔，例如 *.example.com" />
            </el-form-item>
            <el-form-item>
                <template #label>到期时间<PromptButton placement="top" width="440"><div class="credential-help"><div class="credential-help-title">到期时间说明</div><p>凭证的预期到期时间，仅用于定时任务临期提醒，可留空。</p><p>开启自动刷新后，到期前 5 分钟内也会触发一次刷新；未开启自动刷新的凭证到期后会被业务直接拒绝使用。</p><p>留空表示不设置到期时间。</p></div></PromptButton></template>
                <el-date-picker v-model="form.expireTime" type="datetime" placeholder="留空表示不设置" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
            </el-form-item>
            <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
            <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
        </el-collapse-item>
      </el-collapse>
    </el-form>
    <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </el-dialog>
</template>

<script setup>
import { Delete, Plus } from '@element-plus/icons-vue'
import { addCredential, getCredentialSecret, updateCredential } from '@/api/system/credential'

const emit = defineEmits(['saved'])
const { proxy } = getCurrentInstance()
const visible = ref(false)
const saving = ref(false)
const storageStateText = ref('')
const advancedSecretText = ref('')
const targetHostsText = ref('')
const advancedPanels = ref([])
const additionalAuthLoaded = ref(false)
const preservedSecretKeys = ref(new Set())
/* 编辑打开时已保存 secret 的字段快照：输入框被清空的字段会在保存时显式传空串，由后端从旧密文中删除。 */
const savedSecretKeys = ref(new Set())
const requestTemplateInputRefs = {}
const sensitive = reactive({ cookie: '', headerName: '', headerValue: '', valuePrefix: 'Bearer ', token: '', username: '', password: '', otpSecret: '' })
const requestMethods = ['GET', 'POST', 'PUT', 'PATCH']
const credentialTypes = [{ value:'browser_storage',label:'浏览器状态'},{value:'http_cookie',label:'HTTP Cookie'},{value:'http_token',label:'HTTP Token'},{value:'http_api_key',label:'API Key'},{value:'http_header',label:'HTTP Header'}]
const authModes = [{value:'manual',label:'手工录入，不自动更新'},{value:'http_login',label:'HTTP 登录重新获取'},{value:'http_refresh',label:'携带现有凭证刷新（可配兜底登录）'},{value:'browser_login',label:'浏览器人工登录'},{value:'browser_refresh',label:'浏览器刷新'}]
const otpTypes = [{value:'none',label:'不需要'},{value:'totp',label:'TOTP 自动生成'},{value:'sms',label:'短信验证码（需人工/外部服务）'},{value:'email',label:'邮箱验证码（需人工/外部服务）'},{value:'manual',label:'人工确认'}]
const sharingModes = [{value:'shared_read',label:'共享读取'},{value:'exclusive_refresh',label:'刷新时独占'},{value:'exclusive_use',label:'使用期间独占'}]
const assertionOperators = [{ value:'equals', label:'等于' },{ value:'not_equals', label:'不等于' },{ value:'exists', label:'存在' },{ value:'not_empty', label:'非空' },{ value:'contains', label:'包含' },{ value:'in', label:'属于' }]
const additionalHeaders = reactive([])
const additionalCookies = reactive([])
const emptyAssertion = () => ({ source:'', operator:'equals', expectedText:'', message:'' })
const emptyRequest = () => ({ url:'', method:'POST', headersText:'{}', queryText:'{}', bodyText:'{}', dataText:'{}', mappings:[], assertions:[] })
const loginRequest = reactive(emptyRequest())
const refreshRequest = reactive(emptyRequest())
const emptyForm = () => ({ credentialName:'', credentialType:'http_cookie', authMode:'manual', enabled:true, autoRefreshEnabled:false, refreshIntervalSec:0, sharingMode:'shared_read', expireTime:'', authConfig:{ otpType:'none', targetHostPatterns:[] }, remark:'' })
const form = reactive(emptyForm())
const isHttpMode = computed(() => ['http_login', 'http_refresh'].includes(form.authMode))
const supportsAutoRefresh = computed(() => ['http_login', 'http_refresh'].includes(form.authMode))
const showLoginConfig = computed(() => form.authMode === 'http_login')
// HTTP 登录和 HTTP 刷新都复用同一组请求编辑器；http_refresh 会同时展示刷新接口和兜底登录接口。
const requestEditors = computed(() => {
  if (form.authMode === 'http_login') {
    return [{ kind: 'login', label: '登录接口', bodyPlaceholder: '{"username":"${secret.username}","password":"${secret.password}"}', request: loginRequest }]
  }
  if (form.authMode === 'http_refresh') {
    return [
      { kind: 'refresh', label: '刷新接口', bodyPlaceholder: '{}，刷新时当前 Cookie/Header 会自动携带', request: refreshRequest },
      { kind: 'login', label: '兜底登录接口', bodyPlaceholder: '{"username":"${secret.username}","password":"${secret.password}"}', request: loginRequest },
    ]
  }
  return []
})
const hasCookieHeaderPrimary = computed(() => ['http_header', 'http_api_key'].includes(form.credentialType) && sensitive.headerName.trim().toLowerCase() === 'cookie')
const templateVariables = [
  { value:'${secret.username}', label:'登录用户名' },
  { value:'${secret.password}', label:'登录密码' },
  { value:'${secret.otp}', label:'OTP 验证码' },
  { value:'${secret.token}', label:'当前 Token' },
  { value:'${secret.cookie}', label:'当前完整 Cookie' },
  { value:'${secret.headerValue}', label:'主 Header 值', advanced:true },
]
const templateVariableNamePattern = /^[A-Za-z_][A-Za-z0-9_]*$/

watch([() => form.authMode, () => form.authConfig.otpType], ([mode]) => {
  if (mode === 'http_login' || mode === 'http_refresh') ensureLoginRequestDefaults()
  if (!supportsAutoRefresh.value) form.autoRefreshEnabled = false
})
function jsonText(value) { return JSON.stringify(value || {}, null, 2) }
function jsonValueText(value) { return value === undefined ? '' : JSON.stringify(value) }
function restoreRedacted(value) {
  if (Array.isArray(value)) return value.map(restoreRedacted)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, item === '******' ? `\${secret.${key}}` : restoreRedacted(item)]))
}
function mappingRows(mapping) { return Object.entries(mapping || {}).map(([target, source]) => ({ target, source })) }
function assertionRows(assertions) { return (assertions || []).map(item => ({ source:item?.source || '', operator:item?.operator || 'equals', expectedText:jsonValueText(item?.expected), message:item?.message || '' })) }
function replaceRows(target, rows) { target.splice(0, target.length, ...rows) }
function keyValueRows(value) { return value && typeof value === 'object' && !Array.isArray(value) ? Object.entries(value).map(([name, item]) => ({ name, value:String(item) })) : [] }
function resetRequest(target, config, prefix) {
  const template = restoreRedacted(config?.[`${prefix}RequestTemplate`] || {})
  Object.assign(target, emptyRequest(), {
    url: config?.[`${prefix}Url`] || '', method: config?.[`${prefix}Method`] || config?.requestMethod || 'POST',
    headersText: jsonText(template.headers), queryText: jsonText(template.query || template.params),
    bodyText: jsonText(template.body), dataText: jsonText(template.data),
    mappings: mappingRows(config?.[`${prefix}ResponseMapping`] || config?.responseMapping),
    assertions: assertionRows(config?.[`${prefix}SuccessAssertions`]),
  })
}

/** 将解密后的 secret 字典回填到表单敏感字段，编辑时用于回显。 */
function populateFromSecret(secret) {
  if (!secret || typeof secret !== 'object' || !Object.keys(secret).length) return
  savedSecretKeys.value = new Set(Object.keys(secret))
  if (secret.cookie != null) sensitive.cookie = String(secret.cookie)
  if (secret.headerName != null) sensitive.headerName = String(secret.headerName)
  if (secret.headerValue != null) sensitive.headerValue = String(secret.headerValue)
  if (secret.valuePrefix != null) sensitive.valuePrefix = String(secret.valuePrefix)
  if (secret.token != null) sensitive.token = String(secret.token)
  if (secret.username != null) sensitive.username = String(secret.username)
  if (secret.password != null) sensitive.password = String(secret.password)
  if (secret.otpSecret != null) sensitive.otpSecret = String(secret.otpSecret)
  replaceRows(additionalHeaders, keyValueRows(secret.headers))
  replaceRows(additionalCookies, keyValueRows(secret.cookies))
  preservedSecretKeys.value = new Set(Object.keys(secret))
  additionalAuthLoaded.value = true
  if (secret.storageState != null) storageStateText.value = JSON.stringify(secret.storageState, null, 2)
  const standardKeys = ['cookie', 'cookies', 'headerName', 'headerValue', 'valuePrefix', 'token', 'username', 'password', 'otpSecret', 'storageState', 'headers']
  const extra = {}
  for (const [key, value] of Object.entries(secret)) {
    if (!standardKeys.includes(key)) extra[key] = value
  }
  if (Object.keys(extra).length) advancedSecretText.value = JSON.stringify(extra, null, 2)
  if (additionalHeaders.length || additionalCookies.length || advancedSecretText.value.trim()) advancedPanels.value = ['additional-auth']
}
function ensureLoginRequestDefaults() {
  /* 默认登录模板仅在新增凭证时自动注入；编辑已有凭证时尊重用户已保存的内容，避免清空后被再次填回。 */
  if (!form.credentialId && loginRequest.bodyText.trim() === '{}') {
    loginRequest.bodyText = jsonText({ username:'${secret.username}', password:'${secret.password}' })
  }
  if (form.authConfig.otpType !== 'totp') return
  try {
    const body = parseObject(loginRequest.bodyText, 'JSON 请求体')
    if (!Object.values(body).includes('${secret.otp}')) loginRequest.bodyText = jsonText({ ...body, otp:'${secret.otp}' })
  } catch (_) { /* 用户正在编辑 JSON 时不覆盖输入。 */ }
}
/** 将登录接口的 JSON 请求体恢复为默认的账号密码占位模板，由用户显式触发。 */
function restoreLoginBodyTemplate() {
  loginRequest.bodyText = jsonText({ username:'${secret.username}', password:'${secret.password}' })
}
function open(row) {
  Object.assign(form, emptyForm(), row || {}, { authConfig: { ...emptyForm().authConfig, ...(row?.authConfig || {}) } })
  Object.keys(sensitive).forEach(key => { sensitive[key] = key === 'valuePrefix' ? 'Bearer ' : '' })
  storageStateText.value = ''
  advancedSecretText.value = ''
  additionalAuthLoaded.value = false
  preservedSecretKeys.value = new Set()
  savedSecretKeys.value = new Set()
  advancedPanels.value = []
  replaceRows(additionalHeaders, [])
  replaceRows(additionalCookies, [])
  targetHostsText.value = (form.authConfig.targetHostPatterns || []).join(', ')
  resetRequest(loginRequest, form.authConfig, 'login')
  resetRequest(refreshRequest, form.authConfig, 'refresh')
  if (form.authMode === 'http_login' || form.authMode === 'http_refresh') ensureLoginRequestDefaults()
  visible.value = true
  /* 编辑时从后端获取解密后的凭证明文并回填到表单，敏感字段默认 mask 可通过眼睛图标查看 */
  if (row?.credentialId) {
    getCredentialSecret(row.credentialId).then(response => {
      const secret = response?.data
      if (secret) populateFromSecret(secret)
    }).catch(() => { /* 无权限或解密失败时保持字段为空，用户可手动填写 */ })
  }
}function parseObject(text, label) {
  const value = JSON.parse(text || '{}')
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error(`${label}必须是 JSON 对象`)
  return value
}
function setTemplateInputRef(field, component) {
  if (component) requestTemplateInputRefs[field] = component
  else delete requestTemplateInputRefs[field]
}
function resolveRequestEditor(field) {
  const [kind, requestField] = String(field || '').split(':')
  return { request: kind === 'login' ? loginRequest : refreshRequest, requestField }
}
function isJsonStringPosition(source, position) {
  let insideString = false
  let escaped = false
  for (const character of source.slice(0, position)) {
    if (escaped) {
      escaped = false
      continue
    }
    if (insideString && character === '\\') {
      escaped = true
      continue
    }
    if (character === '"') insideString = !insideString
  }
  return insideString
}
function insertTemplateVariable(field, variable) {
  const { request, requestField } = resolveRequestEditor(field)
  const component = requestTemplateInputRefs[field]
  const input = component?.$el?.querySelector('textarea')
  const source = String(request[requestField] || '')
  const start = input?.selectionStart ?? source.length
  const end = input?.selectionEnd ?? source.length
  const insertion = isJsonStringPosition(source, start) ? variable : `"${variable}"`
  request[requestField] = `${source.slice(0, start)}${insertion}${source.slice(end)}`
  const cursor = start + insertion.length
  nextTick(() => {
    const current = requestTemplateInputRefs[field]?.$el?.querySelector('textarea')
    if (!current) return
    current.focus()
    current.setSelectionRange(cursor, cursor)
  })
}
function buildRequest(request) {
  return { headers:parseObject(request.headersText,'请求 Header'), query:parseObject(request.queryText,'查询参数'), body:parseObject(request.bodyText,'JSON 请求体'), data:parseObject(request.dataText,'表单请求体') }
}
function availableTemplateVariableKeys(secret) {
  const keys = new Set([...preservedSecretKeys.value, ...Object.keys(secret || {})])
  const headerValueExists = keys.has('headerValue') || keys.has('header_value')
  if (hasCookieHeaderPrimary.value && headerValueExists) keys.add('cookie')
  if (form.authConfig.otpType !== 'none' && (keys.has('otpSecret') || keys.has('otp_secret'))) keys.add('otp')
  return keys
}
function collectTemplateVariables(value, location, variables) {
  if (typeof value === 'string') {
    const expressions = [...value.matchAll(/\$\{secret\.([^}]*)\}/g)]
    if ((value.match(/\$\{secret\./g) || []).length !== expressions.length) throw new Error(`${location}存在未闭合的凭证变量`)
    for (const expression of expressions) variables.push({ expression:expression[0], name:expression[1], location })
    return
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectTemplateVariables(item, `${location}[${index}]`, variables))
    return
  }
  if (value && typeof value === 'object') Object.entries(value).forEach(([key, item]) => collectTemplateVariables(item, `${location}.${key}`, variables))
}
function validateRequestTemplateVariables(authConfig, secret) {
  const availableKeys = availableTemplateVariableKeys(secret)
  const templates = [
    ['登录请求模板', authConfig.loginRequestTemplate],
    ['刷新请求模板', authConfig.refreshRequestTemplate],
  ]
  for (const [label, template] of templates) {
    const variables = []
    collectTemplateVariables(template, label, variables)
    for (const variable of variables) {
      if (!templateVariableNamePattern.test(variable.name)) throw new Error(`${variable.location}中的变量 ${variable.expression} 格式错误；仅支持 ${'${secret.字段名}'}，字段名只能包含字母、数字和下划线`)
      if (!availableKeys.has(variable.name)) throw new Error(`${variable.location}引用了 ${variable.expression}，但当前凭证没有填写对应的 ${variable.name} 字段；请在登录账号区域填写，或点击"恢复默认模板"后补填账号，不需要账号时请清空该模板中的账号密码变量`)
    }
  }
}
function validateResponseMappingTargets(authConfig) {
  if (!hasCookieHeaderPrimary.value) return
  for (const [label, mapping] of [['登录响应提取规则', authConfig.loginResponseMapping], ['刷新响应提取规则', authConfig.refreshResponseMapping]]) {
    const target = Object.keys(mapping || {}).find(item => item === 'cookies' || item.startsWith('cookies.'))
    if (target) throw new Error(`${label}不能使用 ${target}：主 Header 名称为 Cookie 时，请使用 header.cookie 或 header.cookie.<名称> 写回 Cookie`)
  }
}
function buildMapping(request) {
  return Object.fromEntries(request.mappings.filter(item => item.target.trim() && item.source.trim()).map(item => [item.target.trim(), item.source.trim()]))
}
function buildKeyValue(rows, label, caseInsensitive = false) {
  const result = {}
  const seen = new Set()
  for (const item of rows) {
    const name = item.name.trim()
    const value = item.value
    if (!name && !value) continue
    if (!name) throw new Error(`${label}名称不能为空`)
    const uniqueName = caseInsensitive ? name.toLowerCase() : name
    if (seen.has(uniqueName)) throw new Error(`${label}名称不能重复：${name}`)
    seen.add(uniqueName)
    result[name] = value
  }
  return result
}
function buildAssertions(request) {
  return request.assertions.filter(item => item.source.trim() || item.expectedText.trim() || item.message.trim()).map((item, index) => {
    const source = item.source.trim()
    if (!source) throw new Error(`第 ${index + 1} 条成功断言未填写来源`)
    const requiresExpected = !['exists', 'not_empty'].includes(item.operator)
    if (requiresExpected && !item.expectedText.trim()) throw new Error(`第 ${index + 1} 条成功断言未填写期望值`)
    let expected = null
    if (requiresExpected) {
      try { expected = JSON.parse(item.expectedText) } catch (_) { throw new Error(`第 ${index + 1} 条成功断言的期望值必须是合法 JSON`) }
    }
    return { source, operator:item.operator, expected, message:item.message.trim() }
  })
}
function buildSecret() {
  const secret = {}
  if (form.credentialType === 'http_cookie' && sensitive.cookie.trim()) secret.cookie = sensitive.cookie.trim()
  else if (form.credentialType === 'http_cookie' && savedSecretKeys.value.has('cookie')) secret.cookie = ''
  if (['http_header','http_api_key'].includes(form.credentialType)) {
    if (sensitive.headerName.trim()) secret.headerName = sensitive.headerName.trim()
    else if (savedSecretKeys.value.has('headerName')) secret.headerName = ''
    if (sensitive.headerValue) secret.headerValue = sensitive.headerValue
    else if (savedSecretKeys.value.has('headerValue')) secret.headerValue = ''
  }
  if (form.credentialType === 'http_token') {
    if (sensitive.headerName.trim()) secret.headerName = sensitive.headerName.trim()
    else if (savedSecretKeys.value.has('headerName')) secret.headerName = ''
    if (sensitive.valuePrefix) secret.valuePrefix = sensitive.valuePrefix
    else if (savedSecretKeys.value.has('valuePrefix')) secret.valuePrefix = ''
    if (sensitive.token) secret.token = sensitive.token
    else if (savedSecretKeys.value.has('token')) secret.token = ''
  }
  if (storageStateText.value.trim()) secret.storageState = parseObject(storageStateText.value, 'storageState')
  else if (savedSecretKeys.value.has('storageState')) secret.storageState = ''
  const headers = buildKeyValue(additionalHeaders, '附加 Header', true)
  const cookies = buildKeyValue(additionalCookies, '附加 Cookie')
  const hasCookieHeader = hasCookieHeaderPrimary.value || Object.keys(headers).some(name => name.toLowerCase() === 'cookie')
  if (hasCookieHeader && Object.keys(cookies).length) throw new Error('Cookie Header 与结构化附加 Cookie 不能同时配置')
  if (Object.keys(headers).length || additionalAuthLoaded.value) secret.headers = headers
  if (Object.keys(cookies).length || additionalAuthLoaded.value) secret.cookies = cookies
  if (advancedSecretText.value.trim()) {
    const advanced = parseObject(advancedSecretText.value, '其他敏感字段')
    if ('headers' in advanced || 'cookies' in advanced) throw new Error('额外 Header 和 Cookie 请使用附加认证信息区域配置')
    Object.assign(secret, advanced)
  }
  for (const key of ['username','password','otpSecret']) {
    if (sensitive[key]) secret[key] = sensitive[key]
    else if (savedSecretKeys.value.has(key)) secret[key] = ''
  }
  return secret
}
async function save() {
  try {
    if (!form.credentialName.trim()) return proxy.$modal.msgError('请填写凭证名称')
    if (form.autoRefreshEnabled && !supportsAutoRefresh.value) return proxy.$modal.msgError('当前更新方式不支持自动刷新')
    const secret = buildSecret()
    const authConfig = { ...form.authConfig, targetHostPatterns:targetHostsText.value.split(',').map(v=>v.trim()).filter(Boolean), loginUrl:loginRequest.url, refreshUrl:refreshRequest.url, loginMethod:loginRequest.method, refreshMethod:refreshRequest.method, loginRequestTemplate:buildRequest(loginRequest), refreshRequestTemplate:buildRequest(refreshRequest), loginResponseMapping:buildMapping(loginRequest), refreshResponseMapping:buildMapping(refreshRequest), loginSuccessAssertions:buildAssertions(loginRequest), refreshSuccessAssertions:buildAssertions(refreshRequest) }
    validateRequestTemplateVariables(authConfig, secret)
    validateResponseMappingTargets(authConfig)
    const data = { ...form, expireTime: form.expireTime || null, secret, authConfig }
    saving.value = true
    const request = form.credentialId ? updateCredential(form.credentialId, { ...data, expectedRevision:form.revision }) : addCredential(data)
    await request
    proxy.$modal.msgSuccess('保存成功')
    visible.value = false
    emit('saved')
  } catch (error) {
    proxy.$modal.msgError(error?.message || '配置格式错误')
  } finally { saving.value = false }
}

defineExpose({ open })
</script>

<style scoped>
.section-alert { margin-bottom: 16px; }
.template-editor { width: 100%; display: flex; align-items: flex-start; gap: 8px; }
.template-editor > .el-input { flex: 1; min-width: 0; }
.template-editor :deep(.el-dropdown) { flex: 0 0 auto; margin-top: 2px; }
.credential-collapse { margin-top: 4px; margin-bottom: 16px; }
.url-editor { width: 100%; display: flex; align-items: flex-start; gap: 8px; }
.url-editor > .el-input { flex: 1; min-width: 0; }
.url-editor > .el-button { flex: 0 0 auto; }
.key-value-list { width: 100%; display: flex; flex-direction: column; gap: 8px; }
.key-value-row { width: 100%; display: grid; grid-template-columns: minmax(150px, 1fr) minmax(180px, 1.4fr) 32px; gap: 8px; align-items: center; }
.assertion-row { width: 100%; display: grid; grid-template-columns: minmax(120px, 1.2fr) 110px minmax(120px, 1fr) minmax(120px, 1fr) 32px; gap: 8px; align-items: center; margin-bottom: 8px; }
.mapping-row { display:grid; grid-template-columns: 1fr 1.4fr 32px; gap:8px; margin-bottom:8px; align-items:center; }
.mapping-target { display:flex; align-items:center; gap:8px; min-width:0; }
.mapping-target .el-input { flex:1; min-width:0; }
.unit-text { color:var(--el-text-color-secondary); font-size:13px; }
.credential-help { max-width:100%; }
.credential-help-title { font-weight:600; font-size:14px; margin-bottom:8px; color:#303133; }
.credential-help p { margin:0 0 8px; line-height:1.6; color:#606266; }
.credential-help ul { margin:0 0 8px; padding-left:18px; color:#606266; }
.credential-help ul li { line-height:1.6; }
.credential-help-table { width:100%; border-collapse:collapse; margin-bottom:8px; font-size:13px; }
.credential-help-table th, .credential-help-table td { border:1px solid #ebeef5; padding:6px 10px; text-align:left; }
.credential-help-table th { background:#f5f7fa; color:#303133; font-weight:600; }
.credential-help-table td { color:#606266; }
.credential-help-code { background:#f0f2f5; border-radius:4px; padding:4px 8px; margin-bottom:8px; font-family:monospace; font-size:12px; color:#303133; }
.credential-help-note { margin-top:8px; padding:8px 12px; background:#fdf6ec; border-left:3px solid #e6a23c; border-radius:4px; font-size:13px; color:#606266; }
.credential-help-note p { margin:0; }
.credential-help-note ul { margin:4px 0 0; }
@media (max-width: 768px) {
  .key-value-row, .assertion-row { grid-template-columns: 1fr; }
  .key-value-row :deep(.el-button), .assertion-row :deep(.el-button) { justify-self: end; }
}
</style>
