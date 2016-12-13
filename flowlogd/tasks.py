import celery
from celery import Celery
import time
import random
import socket
import zkcelery
import ConfigParser
from put_flow_logs import get_logs, get_log_enable_account_ids
import utils
import constants

LOG = utils.get_logger()
config = ConfigParser.ConfigParser()
config.read(constants.CONFIG_FILENAME)
broker_url = config.get('rabbitmq', 'broker_url', 'amqp://rabbit:rabbit@127.0.0.1//')
periodic_task_interval = int(config.get('task', 'periodic_task_interval', 300))

app = Celery('tasks', backend='rpc://', broker=broker_url)

@app.task(base=zkcelery.LockTask, bind=True)
def flow_log_periodic_task(self):
    with self.lock() as lock:
        if lock:
            LOG.info("Submitting tasks to collect flowlog for accounts")
            acc_ids = get_log_enable_account_ids()
            for acc_id in acc_ids:
                process_flowlog(acc_id)
            LOG.info("Submitted tasks to collect flowlog for accounts")

@app.task(base=zkcelery.LockTask, bind=True)
def process_flowlog(self, acc_id):
    with self.lock(acc_id) as lock:
        if lock:
            LOG.info("Collecting flowlog for account:{acc_id}".format(acc_id=acc_id))
            get_logs(acc_id)
            LOG.info("Collected flowlog for account:{acc_id}".format(acc_id=acc_id))

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(periodic_task_interval, flow_log_periodic_task.s())

