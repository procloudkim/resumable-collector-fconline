from datetime import datetime, timezone
start = datetime(2025,9,12,14,36,11,tzinfo=timezone.utc)
now = datetime.now(timezone.utc)
d = now - start
print(now.isoformat())
print(start.isoformat())
print(int(d.total_seconds()//3600), 'h', (d.seconds%3600)//60, 'm')
