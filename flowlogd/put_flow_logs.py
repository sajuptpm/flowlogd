import sys
import os
from jcsclient import client
#import put_logs as PS
import create_cross_account_policies as CP
from datetime import datetime , timedelta
import ConfigParser
import json
import getopt
import urllib2
import requests
import pdb
import datetime
import pytz
import write_to_file as WF
import constants
import utils
### Usage info
LOG = utils.get_logger()

# create bucket
def create_bucket(bucket):
    LOG.info(jclient.dss.create_bucket(['create-bucket','--bucket', bucket]))

#put objects into the bucket
def put_logs(directory,bucket,f):
    LOG.info('put object %s into bucket %s' % (f,bucket))
    LOG.info( jclient.dss.put_object(['put-object','--bucket', bucket
                                              ,'--key', 'vpc_flow_logs/'+f
                                              ,'--body', directory+'/'+f]))


def initiate_client(secret):
    LOG.info('initializing jcsclient')
    ##### Change this stuff and make it dynamic
    jclient = client.Client(access_key = secret['access_key'], secret_key = secret['secret_key'],
                            vpc_url=secret['vpc_url'],
                            dss_url=secret['dss_url'],
                            iam_url=secret['iam_url'] )

    return jclient

#global declaration of config file
CONFIG = ConfigParser.ConfigParser()
CONFIG.read(constants.CONFIG_FILENAME)
secret = WF.config_section_map(CONFIG, 'secret')
logs = WF.config_section_map(CONFIG, 'logs')
jclient = initiate_client(secret)

#creating bucket and cross account policy 

def policy_update(config,bucket_name,dss_account_id):
    ''' Give full path of the config file.
        It should have time delt in days.
        Environment
        bucket_name
        policy_name
        policy_action
        resources for that policy
        accounts which should have those policy attached
    '''

    LOG.info('creating bucket %s' % bucket)
    create_bucket(bucket_name)


    account_id = dss_account_id
    resources= []
    for dict1 in config['resources']:
        dict1['account_id']= account_id
        dict1['resource']= 'Bucket:'+bucket_name
        resources.append(dict1)
  
    #creating cross account policy
    CP.create_resource_based_policy(bucket_name,[], [], jclient)
    CP.update_resource_based_policy(bucket_name,config['accounts'], config['actions'], jclient)
    CP.attach_policy_to_resource(bucket_name,resources,jclient)

def write_to_dss(account_id,directory,b_dir,file_name):
    bucket = WF.config_section_map(CONFIG, 'bucket')
    bucket['actions'] = bucket['actions'].split(',')
    bucket['accounts'] = account_id[20:]
    bucket['resources'] = [json.loads(resource) for resource in bucket['resources'].split(',')]
    bucket_name=b_dir
    res = jclient.dss.head_bucket(['head-bucket','--bucket',bucket_name])
    
    if not os.path.exists(directory) or res['status'] != 200:
    	policy_update(bucket,bucket_name,logs['dss_account_id'])
    put_logs(directory,bucket_name,file_name)
    

def get_logs(account_id):
    time_interval = logs['time_interval']
    end_time= datetime.datetime.now()
    start_time= end_time - datetime.timedelta(seconds = int(time_interval))
    base_directory= 'vpc-flow-log-'+account_id[20:]
    directory = '/tmp/'+ base_directory
    file_name= base_directory+'-'+start_time.strftime('%d_%m_%Y-%H_%M')
    start_time= start_time.strftime('%d-%m-%Y %H:%M:%S')
    end_time= end_time.strftime('%d-%m-%Y %H:%M:%S')

    LOG.info('account id: %s start_time: %s end_time: %s' % (account_id,start_time,end_time))
    if not os.path.exists(directory):
        os.makedirs(directory)
        LOG.info('creating directory %s' % directory)
    #below code will create the file and append the output such that json property will not be destroyed

    with open(directory+'/'+file_name, 'a') as outfile:
        outfile.write('{ "log_data" : [')
    if WF.get_log_in_time(start_time,end_time,directory,file_name,account_id,0,'destvn'):
        with open(directory+'/'+file_name, 'a') as outfile:
            outfile.write(',')
    WF.get_log_in_time(start_time,end_time,directory,file_name,account_id,1,'sourcevn')
    with open(directory+'/'+file_name, 'a') as outfile:
        outfile.write(']}')
    
    # create bucket and cross account policy
    write_to_dss(account_id,directory,base_directory,file_name)

def get_log_enable_account_ids():

    res = jclient.vpc.describe_flow_log_enable_accounts('describe-flow-log-enable-accounts')
    return res['DescribeFlowLogEnableAccountsResponse']['accountIds']['item']
