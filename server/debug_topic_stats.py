from module_task.scheduler_maintenance import ticket_topic_stats_report, pull_feishu_bitable_ticket_sync

# result = ticket_topic_stats_report(
#   startDate="2026-06-23",
#   endDate="2026-06-23",
#   appId="cli_a9523b9e7f389cb0",
#   appSecret="t8PhCkW2Cr5z27KzmxiaefmMzbhiYVmp",
#   send=False,
#   keyword="TRunner",
#   pageSize=30,
#   sources=[
#       {
#           "name": "RTA POS P2 工单群",
#           "chatId": "oc_fd391a88b21ebcafc3d1d69356909147",
#           "priority": "P2",
#       },
# {
#           "name": "RTA POS P3/P4工单群",
#           "chatId": "oc_15203ab07d26c830240fdb9caa8de501",
#           "priority": "P3",
#       }
#   ],
# receive_chat_ids=["oc_8ac97f03b8b8ff7c0ddfb776beede921"]
# )
#
# print(result)

data = pull_feishu_bitable_ticket_sync()
print(data)