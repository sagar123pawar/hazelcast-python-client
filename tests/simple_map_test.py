import threading
import random
import time
import logging
import sys

from os.path import dirname

sys.path.append(dirname(dirname(__file__)))

import hazelcast

THREAD_COUNT = 10
ENTRY_COUNT = 10 * 1000
VALUE_SIZE = 10000
GET_PERCENTAGE = 40
PUT_PERCENTAGE = 40

logging.basicConfig(format='%(asctime)s%(msecs)03d [%(name)s] %(levelname)s: %(message)s', datefmt="%H:%M%:%S,")
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger("main")

config = hazelcast.Config()
config.username = "dev"
config.password = "dev-pass"
config.addresses.append("127.0.0.1:5701")
client = hazelcast.HazelcastClient(config)


class ClientThread(threading.Thread):
    def __init__(self, name):
        threading.Thread.__init__(self, name=name)
        self.gets = 0
        self.puts = 0
        self.removes = 0
        self.setDaemon(True)

    def run(self):
        my_map = client.get_map("default")
        while True:
            key = int(random.random() * ENTRY_COUNT)
            operation = int(random.random() * 100)
            if operation < GET_PERCENTAGE:
                my_map.get(key)
                self.gets += 1
            elif operation < GET_PERCENTAGE + PUT_PERCENTAGE:
                my_map.put(key, "x" * VALUE_SIZE)
                self.puts += 1
            else:
                my_map.remove(key)
                self.removes += 1


threads = [ClientThread("client-thread-%d" % i) for i in xrange(0, THREAD_COUNT)]
for t in threads:
    t.start()

start = time.time()
counter = 1
while counter < 1000:
    time.sleep(5)
    print "ops per second : " + \
          str(sum([t.gets + t.puts + t.removes for t in threads]) / (time.time() - start))
    for t in threads:
        print ("%s: put: %d get: %d: remove: %d" % (t.name, t.puts, t.gets, t.removes))
    counter += 1