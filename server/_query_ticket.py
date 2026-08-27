import os, json
os.environ['APP_ENV'] = 'prod'
from dotenv import load_dotenv
load_dotenv('.env.prod')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

db_url = (
    "mysql+pymysql://" + os.environ['DB_USERNAME'] + ":" + os.environ['DB_PASSWORD']
    + "@" + os.environ['DB_HOST'] + ":" + os.environ['DB_PORT'] + "/" + os.environ['DB_DATABASE'] + "?charset=utf8mb4"
)
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
db = Session()

ticket = db.execute(text(
    "SELECT ticket_id, status, extra_data FROM ticket WHERE ticket_no = 'INC00001881151'"
)).fetchone()
print(f"status列: [{ticket[1]}]")
extra = json.loads(ticket[2]) if isinstance(ticket[2], str) else (ticket[2] or {})
if isinstance(extra, dict):
    print(f"extra_data.ticketStatus: [{extra.get('ticketStatus', 'N/A')}]")
    print(f"extra_data.ticketModle: [{extra.get('ticketModle', 'N/A')}]")

# 检查哪些工单的status是中文的
print("\n=== 中文status工单数量 ===")
cnt = db.execute(text("SELECT COUNT(*) FROM ticket WHERE status LIKE '%Pending%'")).fetchone()
print(f"包含'Pending'的工单: {cnt[0]}")

cnt2 = db.execute(text("SELECT COUNT(*) FROM ticket WHERE status LIKE 'processing_%' OR status LIKE 'dev_done' OR status LIKE 'wait_%' OR status = 'closed'")).fetchone()
print(f"内部编码的工单: {cnt2[0]}")

db.close()
