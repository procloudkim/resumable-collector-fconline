from datetime import datetime, timezone, timedelta
start_local = datetime(2025,9,12,14,36,11)
# assume KST (UTC+9)
start_utc = start_local - timedelta(hours=9)
now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
d = now_utc - start_utc
print('start_local', start_local.isoformat())
print('start_utc', start_utc.isoformat())
print('now_utc', now_utc.isoformat())
print(int(d.total_seconds()//3600),'h', (d.seconds%3600)//60, 'm')
