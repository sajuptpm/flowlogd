import celery
from celery import Celery
import time
import random
import socket
import zkcelery
import ConfigParser
from put_flow_logs import get_logs, get_log_enable_account_ids

config = ConfigParser.ConfigParser()
config.read('/etc/vpc_flow_logs.cfg')
broker_url = config.get('rabbitmq', 'broker_url', 'amqp://rabbit:rabbit@127.0.0.1//')
periodic_task_interval = config.get('tasks', 'periodic_task_interval', 300)

app = Celery('tasks', backend='rpc://', broker=broker_url)

@app.task(base=zkcelery.LockTask, bind=True)
def flow_log_periodic_task(self):
    with self.lock() as lock:
        if lock:
            do_work()

def do_work():
    acc_ids = get_log_enable_account_ids()
    for acc_id in acc_ids:
        get_logs(acc_id)    

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(periodic_task_interval, flow_log_periodic_task.s())

