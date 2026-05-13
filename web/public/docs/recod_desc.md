结论

  - 这条链路是“Web 后端下发录制命令 -> Agent 客户端实时采集 -> 通过 Agent WebSocket 回传 -> 后端按事件落库 -> Web 前端轮询详情接口重建并展示”。
  - 真正实时入库的是 record_event 这类步骤事件，落到 hrm_web_recording_event；record_status、record_finished、record_error 主要更新 hrm_web_recording_session，不直接写步骤事件表。
  - Web 前端不是直连客户端推送，而是按固定轮询从后端拉 GET /hrm/web-case/recording/{recordingId}，再把返回的 events 和 steps 渲染到页面。

  具体流程

  1. Web 端发起录制

  - POST /hrm/web-case/recording/start 进入 [server/module_hrm/controller/web_case_controller.py](server/module_hrm/controller/web_case_controller.py#L497)，再进入 [server/module_hrm/service/
    web_case_service.py](server/module_hrm/service/web_case_service.py#L2962)。
  - start_recording_services 先创建 hrm_web_recording_session，状态置为录制中，然后组装 {"requestType": webui, "command": "start_recording", ...}。
  - 这个命令通过 send_message 发给 Agent，send_message 用的是 WebSocket，并把请求压成 request_chunk 分片发送。对应代码在 [server/module_qtr/service/agent_service.py](server/module_qtr/service/
    agent_service.py#L43) 和 [server/module_hrm/service/web_case_service.py](server/module_hrm/service/web_case_service.py#L3077)。

  2. Agent 客户端收到开始录制命令

  - Agent 侧 WebSocket 收到消息后，在 [server/module_qtr/controller/agent_controller.py](server/module_qtr/controller/agent_controller.py#L241) 的接收循环里重组消息。
  - 如果是分片消息，先合并 response_chunk 或 event_chunk，再交给 _dispatch_agent_event 分发。
  - 对 start_recording 命令，最终进入 [client_new/services/web_test_service.py](client_new/services/web_test_service.py#L2304) 的 handle_request，再分派到 _start_recording。

  3. 客户端开始采集浏览器事件

  - _start_recording 在 [client_new/services/web_test_service.py](client_new/services/web_test_service.py#L2437) 创建 RecorderSession，启动浏览器、创建上下文、打开页面。
  - _enable_recording_capture 在 [client_new/services/web_test_service.py](client_new/services/web_test_service.py#L2610) 里做两件关键事：
  - 注入 RECORDER_SCRIPT。
  - expose_binding("__qtrRecordEvent", _event_binding)，让浏览器脚本可以把录制结果回传到 Python。
  - 浏览器侧脚本触发时，_event_binding 会把 payload 转成字典，再调用 session.emit(payload)。
  - RecorderSession.emit 在 [client_new/services/web_test_service.py](client_new/services/web_test_service.py#L2147) 会先自增 event_index，再把统一消息发给后端：
      - type
      - recording_id
      - event_index
      - payload
  - 默认事件类型是 record_event，页面跳转会走 _handle_navigation，停止录制会走 _stop_recording。

  4. 客户端上报的消息类型
     | type | 触发场景 | 后端处理方式 |
     |---|---|---|
     | record_event | 普通录制步骤，比如点击、输入、断言等 | 写入 hrm_web_recording_event |
     | record_status | 页面跳转、手动登录等待、录制状态变化 | 只更新 hrm_web_recording_session |
     | record_finished | 录制结束 | 更新会话为已完成，写摘要 |
     | record_error | 录制异常 | 更新会话为失败，写错误信息 |

  后端如何入库

  1. 统一入口

  - Agent 收到客户端上报后，agent_controller 会把 record_event、record_status、record_finished、record_error 这些消息交给 [server/module_hrm/service/web_case_service.py](server/module_hrm/service/
    web_case_service.py#L4123) 的 handle_agent_recording_event。
  - 这一步的关键点是：后端处理的是“消息流”，不是“页面 step 列表”。

  2. record_event 入库

  - 先拿 recording_id 定位会话。
  - event_index 优先用客户端带来的值；如果客户端没带，就用 DAO 的 get_next_recording_event_index 补一个。
  - 再构造 HrmWebRecordingEvent：
      - recording_id
      - event_index
      - event_type 从 payload.actionType / payload.eventType 推出来
      - payload_json 存原始 payload
  - 然后调用 WebCaseDao.add_recording_event 写入 hrm_web_recording_event，同时把会话表更新为录制中、刷新 last_event_at、更新 agent_code，最后 commit。
  - 相关 DAO 在 [server/module_hrm/dao/web_case_dao.py](server/module_hrm/dao/web_case_dao.py#L186)，表结构在 [server/module_hrm/entity/do/web_case_do.py](server/module_hrm/entity/
    do/web_case_do.py#L270)。

  3. record_status 只改会话，不进事件表

  - record_status 分支只更新 hrm_web_recording_session 的 last_event_at 和 result_summary_json，然后提交。
  - 这意味着像“页面跳转”“等待手动登录”这种状态消息，不会出现在 events 表里，只会反映在会话摘要和当前状态上。
  - 这点很关键，因为它决定了 Web 前端看到的是“状态”而不是“步骤”。

  4. record_finished / record_error 结束会话

  - record_finished 会把会话置为已完成，写入 ended_at、last_event_at、result_summary_json，清空 error_message，然后 commit。
  - record_error 会把会话置为失败，写入 ended_at、last_event_at、error_message、result_summary_json，然后 commit。
  - 这两个分支在提交后都会继续同步运行时状态到浏览器会话，保证录制结果和运行态一致。

  后端如何重建步骤

  1. 读取接口

  - Web 前端拉详情走 GET /hrm/web-case/recording/{recordingId}，入口在 [server/module_hrm/controller/web_case_controller.py](server/module_hrm/controller/web_case_controller.py#L623)。
  - 控制器调用 [server/module_hrm/service/web_case_service.py](server/module_hrm/service/web_case_service.py#L2914) 的 recording_detail_services。

  2. 查询顺序

  - 先查 hrm_web_recording_session。
  - 再查 hrm_web_recording_event，DAO 按 event_index asc, create_time asc 排序。
  - 这表示“步骤顺序”并不是前端自己猜的，而是后端按事件序号重新排序后生成的。

  3. 事件 -> 步骤

  - _build_steps_from_recording_events 会遍历事件列表，按事件负载重建 WebStepModel。
  - _normalize_recording_step 会把 payload 强校验成步骤模型，缺 stepName 时补默认名，缺 record_origin 时补 "recording"。
  - 如果碰到断言拾取类事件，_attach_recording_assertion_to_previous_step 会把断言挂到上一条步骤上，而不是新建一步。
  - 也就是说，后端保存的是“原始事件”，返回给前端的是“重建后的步骤视图”。

  4. 返回给前端的数据

  - WebRecordingDetailModel 里同时返回：
      - 会话信息
      - events
      - steps
  - 前端看到的步骤列表，其实就是这份 detail 里的 steps。

  Web 前端如何反馈展示

  1. 轮询，不是推送

  - 录制中的实时刷新在 [web/src/views/hrm/webcase/composables/useRecordingManager.js](web/src/views/hrm/webcase/composables/useRecordingManager.js#L576)。
  - startRecordingPoll() 每 3000ms 调一次 refreshRecording()。
  - refreshRecording() 再去调 getWebRecording(recordingId)，也就是后端详情接口。
  - 详情弹窗也是同一套路：openRecordingDetail() 打开后，每 3000ms 调 refreshRecordingDetail()。

  2. 前端如何更新本地状态

  - updateLiveRecording(detail) 会把后端返回值同步到：
      - recordingDetail
      - recordingEvents
      - liveRecordingSteps
      - recordingDetailText
  - 相关逻辑在 [web/src/views/hrm/webcase/composables/useRecordingManager.js](web/src/views/hrm/webcase/composables/useRecordingManager.js#L601)。
  - 这意味着 UI 不是直接绑定数据库，而是绑定本地响应式状态，本地状态来自后端轮询结果。

  3. 页面上具体渲染什么

  - [web/src/views/hrm/webcase/components/RecordingLiveDialogs.vue](web/src/views/hrm/webcase/components/RecordingLiveDialogs.vue#L480) 的“步骤列表”直接用 liveRecordingSteps。
  - 同一个弹窗的“步骤JSON”直接用 recordingDetailText。
  - 详情弹窗里的步骤预览、事件列表、JSON 也是从 recordingDetail 派生出来的。

  关键处理方式

  - 客户端侧的 event_index 是先在本地自增，再上报，后端以它为主，缺失时才兜底生成。
  - 事件表存的是原始 payload，步骤表视图是读时重建，不是写时固化。
  - record_event 是真正的步骤写入；record_status 只是状态/摘要更新。
  - Web 前端没有订阅后端事件流，当前实现是“轮询拉详情”。
  - 所以你看到的“实时”，本质上是“事件实时入库 + 前端定时刷新”。

  改动文件

  - 无。本次只是按现有代码做流程分析，没有改动代码。

  验证结果

  - 未执行构建或测试，因为这次需求是只分析、不改动代码。
  - 已基于现有代码定位到完整链路：客户端采集、Agent WebSocket 传输、后端入库、前端轮询展示。

  风险与下一步

  - record_status 不进事件表，所以如果你期待“页面跳转/手动登录状态”也出现在步骤列表里，现有代码不会这样做。
  - 如果你要，我可以继续把这条链路整理成一张“时序图 + 字段对照表”，把每个消息体字段和数据库字段一一对应出来。