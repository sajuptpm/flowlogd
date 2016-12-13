import datetime,pytz
import requests
import ConfigParser
import constants
import utils
#import put_flow_logs as pflow
LOG = utils.get_logger()

field = ('{"limit": 100000, "select_fields": ['
           '"sourcevn", "sourceip", "destvn", "destip", "protocol", '
           '"sport", "dport",  "direction_ing", "setup_time", '
           '"teardown_time","agg-packets", "agg-bytes", "action", '
           '"sg_rule_uuid", "nw_ace_uuid",  "underlay_proto", '
           '"underlay_source_port","UuidKey"],'
           '"table": "FlowRecordTable",')



def config_section_map(CONFIG, section):
    dict1 = {}
    options = CONFIG.options(section)
    for option in options:
        try:
            dict1[option] = CONFIG.get(section, option)
            if dict1[option] == -1 :
                print "Wrong Option"
        except:
            dict1[option]  = None
    return dict1




def convert_to_now(time):
    current_time= datetime.datetime.now()
    t_time= datetime.datetime.strptime(time, '%d-%m-%Y %H:%M:%S')
    '''
    # this code for converting IST to UCT
    local = pytz.timezone ("Asia/Kolkata")
    local_dt = local.localize(t_time, is_dst=None)
    utc_dt = local_dt.astimezone (pytz.utc)
    utcdt = utc_dt.replace(tzinfo=None)
    delta=int( (current_time - utcdt).total_seconds())
    '''
    delta=int( (current_time - t_time).total_seconds())
    now_time= 'now-%ss' % (delta)
    return now_time


#this function will query the log from contrail and if it failed it will  retry till n_try.
def write_log_to_file(start_time,end_time,directory,file_name,account_id,dirn,vn,logs):
    n_try= logs['n_try']
    url = logs['url']
    data = field + ('"end_time": "%s" , "start_time": "%s", "dir": %s, "filter": [[{"name": '
            '"%s", "value": ".*%s.*", '
            '"op": 8}]] }') % (end_time, start_time, dirn, vn, account_id)
    LOG.info(data)
    count=0
    while True:
        try:
            req = requests.post(url, data, headers = {'Content-Type': 'application/json'})
        except requests.exceptions.RequestException as e:
            print e
            continue
        value=req.text
        if len(value) <= 3 and count < n_try:
            count = count+1
            LOG.info('query fail for start_time: %s end_time: %s  try count: %s ' % (start_time,end_time,count))
            continue
        elif count >= n_try:
            return False
        else:
            LOG.info('query successfull for start_time: %s end_time: %s ' % (start_time,end_time))
            with open(directory+'/'+file_name, 'a') as outfile:
                outfile.write(value)
            return True


#This function will devide the query on the basis of time_delta defined in config file
# and call write_log_to_file to get the query and write it to the file
def get_log_in_time(start_time,end_time,directory,file_name,account_id,dirn,vn):
    CONFIG = ConfigParser.ConfigParser()
    CONFIG.read(constants.CONFIG_FILENAME)
    logs = config_section_map(CONFIG, 'logs')
    s_t = datetime.datetime.strptime(start_time, '%d-%m-%Y %H:%M:%S')
    e_t = datetime.datetime.strptime(end_time, '%d-%m-%Y %H:%M:%S')
    temp = s_t
    while True:
        temp1=temp
        temp = temp + datetime.timedelta(seconds = int(logs['time_delta']))
        total_seconds = (e_t - temp).total_seconds()
	LOG.info('query logs for start_time: %s end_time: %s' % (temp1,temp))
        if write_log_to_file(convert_to_now(temp1.strftime('%d-%m-%Y %H:%M:%S')),convert_to_now(temp.strftime('%d-%m-%Y %H:%M:%S')),directory,file_name,account_id,0,vn,logs):
            if total_seconds > 1:
                with open(directory+'/'+file_name, 'a') as outfile:
                    outfile.write(',')
        else:
            if total_seconds <= 0:
                return False
        if total_seconds <= 0:
            return True

