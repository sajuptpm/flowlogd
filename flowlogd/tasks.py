import json
import time
import celery
from celery import Celery
from celery import group
import kazoo.client
import zkcelery
import ConfigParser
import utils
import constants
from put_flow_logs import get_logs, get_log_enable_account_ids

LOG = utils.get_logger()
config = ConfigParser.ConfigParser()
config.read(constants.CONFIG_FILENAME)
broker_url = config.get('rabbitmq', 'broker_url', 'amqp://rabbit:rabbit@127.0.0.1//')
periodic_task_interval = int(config.get('task', 'periodic_task_interval', 300))

app = Celery('tasks', backend='rpc://', broker=broker_url)


class FlowlogTask(zkcelery.LockTask):

    def get_or_create_node(self, path, value='', acl=None,
                        ephemeral=False, sequence=False, makepath=False):
        client = None
        hosts = getattr(self.app.conf, 'ZOOKEEPER_HOSTS', '127.0.0.1:2181')
        try:
            client = kazoo.client.KazooClient(hosts=hosts)
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
        hosts = getattr(self.app.conf, 'ZOOKEEPER_HOSTS', '127.0.0.1:2181')
        try:
            client = kazoo.client.KazooClient(hosts=hosts)
            client.start()
            client.set(path, value)
        except Exception as ex:
            raise ex
        finally:
            if client:
                client.stop()
                client.close()


def get_next_start_time(node_data):
    if node_data and isinstance(node_data, tuple):
        data = node_data[0]
        if data:
            try:
                ldata = json.loads(data)
            except Exception as ex:
                LOG.error(ex)
                raise ex
            if ldata and isinstance(ldata, dict):
                return ldata.get('end_time')


@app.task(base=FlowlogTask, bind=True)
def flow_log_periodic_task(self):
    with self.lock() as lock:
        if not lock:
            LOG.info("Periodic task already running on another node")
        else:
            LOG.info("Submitting tasks to collect flowlog for accounts")
            acc_ids = get_log_enable_account_ids()
            for acc_id in acc_ids:
                start_time = None
                path = constants.ZK_FLOWLOG_PATH.format(acc_id=acc_id)
                node_data = self.get_or_create_node(path, makepath=True)
                start_time = get_next_start_time(node_data)
                process_flowlog.apply_async(args=[acc_id],
                                            kwargs={'start_time': start_time})
                LOG.info("Submitted task to collect flowlog for account:{acc_id}, start_time:{start_time}".\
                    format(acc_id=acc_id, start_time=start_time))
            LOG.info("Submitted tasks to collect flowlog for accounts")
            time.sleep(periodic_task_interval)#To avoid periodic task overlap


@app.task(base=FlowlogTask, bind=True)
def process_flowlog(self, acc_id, start_time=None):
    with self.lock(acc_id) as lock:
        if not lock:
            LOG.info("Task for account:{acc_id} already running on another node".format(acc_id=acc_id))
        else:
            LOG.info("Collecting flowlog for account:{acc_id}".format(acc_id=acc_id))
            end_time = get_logs(acc_id)
            path = constants.ZK_FLOWLOG_PATH.format(acc_id=acc_id)
            node_data = json.dumps({'end_time':end_time})
            self.set_value(path, node_data)
            LOG.info("Collected flowlog for account:{acc_id}".format(acc_id=acc_id))


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(periodic_task_interval, flow_log_periodic_task.s())