
from collections import defaultdict
class EventBus:
    def __init__(self):
        self._s=defaultdict(list)
    def subscribe(self,e,cb):
        self._s[e].append(cb)
    def publish(self,e,p=None):
        for cb in self._s[e]:
            cb(p)
