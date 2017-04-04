from datetime import datetime, timedelta
import json
import socket
from celery import Celery
from celery import chain
import kazoo.client
import zkcelery
import ConfigParser
import utils
import constants
from put_flow_logs import get_logs, get_log_enable_account_ids

LOG = utils.get_logger()
config = ConfigParser.ConfigParser()
config.read(constants.CONFIG_FILENAME)
broker_url = config.get('rabbitmq', 'broker_url',
                        'amqp://rabbit:rabbit@127.0.0.1//')
periodic_task_interval = int(config.get('task', 'periodic_task_interval', 3600))
flowlog_time_interval = int(config.get('logs', 'time_interval', 3600))
delta_correction_tasks_count = int(config.get('task', 'delta_correction_tasks_count', 12))
zookeeper_hosts = config.get('zookeeper', 'hosts', 'localhost:2181')

app = Celery('tasks', backend='rpc://', broker=broker_url)
app.conf.ZOOKEEPER_HOSTS = zookeeper_hosts


class FlowlogTask(zkcelery.LockTask):

    def get_kazoo_client(self):
        hosts = getattr(self.app.conf, 'ZOOKEEPER_HOSTS', '127.0.0.1:2181')
        return kazoo.client.KazooClient(hosts=hosts)

    def get_or_create_node(self, path, value='', acl=None,
                           ephemeral=False, sequence=False, makepath=False):
        client = None
        try:
            client = self.get_kazoo_client()
            client.start()
            if not client.exists(path):
                client.create(path, value=value, acl=acl, ephemeral=ephemeral,
                              sequence=sequence, makepath=makepath)
            return client.get(path)
        except Exception as ex:
            raise ex
        finally:
            if client:
                client.stop()
                client.close()

    def set_value(self, path, value):
        client = None
        try:
            client = self.get_kazoo_client()
            client.start()
            client.set(path, value)
        except Exception as ex:
            raise ex
        finally:
            if client:
                client.stop()
                client.close()

def parse_node_data(node_data):
    if node_data and isinstance(node_data, tuple):
        data = node_data[0]
        if data:
            ldata = None
            try:
                ldata = json.loads(data)
            except Exception as ex:
                LOG.error(ex)
            if ldata and isinstance(ldata, dict):
                return ldata

def can_run_periodic_task(node_data):
    data = parse_node_data(node_data)
    if data:
        ptask_start_time = data.get('next_start_time')
        updated_by = data.get('updated_by')
        if ptask_start_time:
            start_time = datetime.strptime(ptask_start_time,
                                           constants.DATETIME_FORMAT)
            if not datetime.now() >= start_time:
                LOG.info('Periodic task already processed by node:'
                         '{updated_by}, next trigger is scheduled on:'
                         '{ptask_start_time}'.format(
                            updated_by=updated_by,
                            ptask_start_time=ptask_start_time))
                return False
    return True

def check_delta(data, parse=False):
    if parse:
        data = parse_node_data(data)
    delta = False
    if data:
        start_time = data.get('next_start_time')
        if start_time:
            start_time = datetime.strptime(start_time,
                                           constants.DATETIME_FORMAT)
            if start_time < (datetime.now() - timedelta(
                        seconds=2*int(flowlog_time_interval))):
                delta = True
    return delta

def check_overflow(data, parse=False):
    if parse:
        data = parse_node_data(data)
    if data:
        start_time = data.get('next_start_time')
        if start_time:
            start_time = datetime.strptime(start_time,
                                           constants.DATETIME_FORMAT)
            now = datetime.now()
            end_time = start_time + timedelta(seconds=int(flowlog_time_interval))
            if now < end_time:
                LOG.info('Detected overflow, current time:{now}, '
                         'start_time:{start_time} '
                         'end_time:{end_time}'
                         ''.format(now=now, start_time=start_time, end_time=end_time))
                return True
    return False

def correct_delta(acc_id, data):
    start_time = updated_by = None
    if data:
        start_time = data.get('next_start_time')
        if start_time:
            start_time = datetime.strptime(start_time,
                                           constants.DATETIME_FORMAT)
            time_delta = datetime.now() - start_time
            time_delta_sec = time_delta.total_seconds()
            est_tasks_count = int(time_delta_sec) / int(flowlog_time_interval)
            if est_tasks_count > delta_correction_tasks_count:
                tasks_count = delta_correction_tasks_count
            else:
                tasks_count = est_tasks_count
            start_time_str = start_time.strftime(constants.DATETIME_FORMAT)
            LOG.info('Correcting delta for account:{acc_id}, '
                     'start_time:{start_time}, time_delta_sec: {time_delta_sec} '
                     'delta_correction_tasks_count: {tasks_count}'.format(
                        acc_id=acc_id, start_time=start_time_str,
                        time_delta_sec=time_delta_sec, tasks_count=tasks_count))
            if tasks_count:
                _tasks = [process_flowlog.s(start_time_str, acc_id)]
                _tasks.extend([process_flowlog.s(acc_id) for x in range(1, tasks_count)])
                chain(tuple(_tasks)).delay()

def submit_process_flowlog_task(acc_id, data):
    start_time = updated_by = None
    if data:
        start_time = data.get('next_start_time')
        updated_by = data.get('updated_by')
    process_flowlog.apply_async(args=[start_time, acc_id])
    LOG.info('Submitted task to collect flowlog for account:{acc_id},'
             ' start_time:{start_time},'
             ' last updated by node:{updated_by}'.format(
                acc_id=acc_id, start_time=start_time,
                updated_by=updated_by))

@app.task(base=FlowlogTask, bind=True)
def flow_log_periodic_task(self):
    pt_start_time = datetime.now() - timedelta(seconds=10)
    acc_task_next_start_time = None
    with self.lock() as lock:
        if not lock:
            LOG.info("Periodic task already running on another node")
        else:
            node_data = self.get_or_create_node(constants.ZK_PTASK_PATH,
                                                makepath=True)
            if not can_run_periodic_task(node_data):
                return None
            LOG.info("Submitting tasks to collect flowlog for accounts")
            acc_ids = get_log_enable_account_ids()
            for acc_id in acc_ids:
                path = constants.ZK_ACC_PATH.format(acc_id=acc_id)
                node_data = self.get_or_create_node(path, makepath=True)
                data = parse_node_data(node_data)
                if check_delta(data):
                    correct_delta(acc_id, data)
                else:
                    if check_overflow(data):
                        LOG.info('Detected overflow for account:{acc_id}'
                                 ''.format(acc_id=acc_id))
                    else:
                        submit_process_flowlog_task(acc_id, data)
            next_start_time = pt_start_time + timedelta(
                                seconds=int(periodic_task_interval))
            next_start_time_str = next_start_time.strftime(
                                    constants.DATETIME_FORMAT)
            node_data = json.dumps({'next_start_time': next_start_time_str,
                                    'updated_by': socket.gethostname()})
            self.set_value(constants.ZK_PTASK_PATH, node_data)
            LOG.info('Submitted tasks to collect flowlog for accounts,'
                     ' Periodic task will run again on:'
                     '{next_start_time_str}'.format(
                        next_start_time_str=next_start_time_str))

@app.task(base=FlowlogTask, bind=True)
def process_flowlog(self, start_time, acc_id):
    with self.lock(acc_id) as lock:
        if not lock:
            LOG.info('Task for account:{acc_id} already running'
                     ' on another node'.format(acc_id=acc_id))
        else:
            LOG.info('Collecting flowlog for account:'
                     '{acc_id}, from:{from_time}'.format(
                        acc_id=acc_id, from_time=start_time))
            next_start_time = get_logs(acc_id, start_time=start_time)
            path = constants.ZK_ACC_PATH.format(acc_id=acc_id)
            node_data = json.dumps({'next_start_time': next_start_time,
                                    'updated_by': socket.gethostname()})
            self.set_value(path, node_data)
            LOG.info('Collected flowlog for account:{acc_id}, '
                     'from:{from_time} to:{to_time}'.format(
                        acc_id=acc_id, from_time=start_time,
                        to_time=next_start_time))
            return next_start_time

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(periodic_task_interval,
                             flow_log_periodic_task.s())
