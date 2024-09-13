from datetime import datetime, timezone, timedelta

print(datetime.utcnow().timestamp(), datetime.now().timestamp(), datetime.now(timezone.utc).timestamp())
print(datetime.fromtimestamp(datetime.utcnow().timestamp()).astimezone(
    timezone(timedelta(hours=16))).strftime("%Y-%m-%d %H:%M:%S"))

now = datetime.now(timezone.utc)
print(now.timestamp())
date1 = datetime.fromtimestamp(now.timestamp())
print(date1.strftime("%Y-%m-%d %H:%M:%S"))

date = datetime.fromtimestamp(now.timestamp(), timezone.utc).astimezone(
                                             timezone(timedelta(hours=8)))

print(date.strftime("%Y-%m-%d %H:%M:%S"))
