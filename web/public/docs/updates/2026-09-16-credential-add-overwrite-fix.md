# 修复新增凭证误覆盖旧凭证的问题

- **现象**：先编辑过某个凭证（或打开过编辑弹窗）后，再点「新增凭证」保存，请求实际走了更新接口，把旧凭证内容覆盖成新填写的数据。
- **根因**：凭证弹窗的 `emptyForm()` 未包含 `credentialId` 和 `revision` 字段，`open()` 用 `Object.assign(form, emptyForm(), row)` 重置表单时无法清掉上次编辑残留的主键；保存时 `form.credentialId ? updateCredential(...) : addCredential(...)` 因此误走更新分支。
- **修复**：`emptyForm()` 补充 `credentialId: ''` 与 `revision: 0`，每次打开弹窗都彻底重置主键与版本号；编辑路径由 `row` 正常回填，不受影响。
- **关联**：此前「到期时间留空报 400」的错误恰好拦截了该误更新；expireTime 空串归一为 null 的修复上线后，该误覆盖从报错变为静默成功，问题由此暴露。
- **注意**：如果此前在"新增"时实际覆盖了旧凭证，被覆盖的凭证数据不会自动恢复，需要人工重新编辑该凭证或删除后重建。
- 业务绑定弹窗的 `emptyBinding()` 本身包含 `bindingId: ''`，无此问题。