from datetime import datetime, timezone
start = datetime(2020,5,20,0,0,0,tzinfo=timezone.utc)
now = datetime.now(timezone.utc)
delta = now - start
hours = int(delta.total_seconds()//3600)
print(now.isoformat())
print(hours)
