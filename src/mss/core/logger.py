
from datetime import datetime
class Logger:
    def info(self,msg):
        print(f"[{datetime.now():%H:%M:%S}] INFO {msg}")
