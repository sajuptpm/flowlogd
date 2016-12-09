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
import logging
import pdb
import datetime
import pytz
import write_to_file as WF
### Usage info

LOG_FILENAME = 'Flow_Logs.log'
logging.basicConfig(filename=LOG_FILENAME,
                        level=logging.DEBUG,
                        )



def create_bucket(bucket, jclient):
    logging.info(jclient.dss.create_bucket(['create-bucket','--bucket', bucket]))

def put_logs(directory,bucket, jclient,f):
    logging.info( jclient.dss.put_object(['put-object','--bucket', bucket
                                              ,'--key', 'vpc_flow_logs/'+f
                                              ,'--body', directory+'/'+f]))

    logging.info( jclient.dss.list_objects(['list-objects','--bucket',bucket]))


def initiate_client(secret):
    ##### Change this stuff and make it dynamic
    jclient = client.Client(access_key = secret['access_key'], secret_key = secret['secret_key'],
                            vpc_url=secret['vpc_url'],
                            compute_url=secret['compute_url'],
                            dss_url=secret['dss_url'],
                            iam_url=secret['iam_url'] )

    return jclient

def policy_update(config,secret,bucket_name,jclient,dss_account_id):
    ''' Give full path of the config file.
        It should have time delt in days.
        Environment
        bucket_name
        policy_name
        policy_action
        resources for that policy
        accounts which should have those policy attached
    '''

    create_bucket(bucket_name,jclient)


    account_id = dss_account_id
    resources= []
    #if resource policy is changed
    for dict1 in config['resources']:
        dict1['account_id']= account_id
        dict1['resource']= 'Bucket:'+bucket_name
        resources.append(dict1)

    CP.create_resource_based_policy(bucket_name,[], [], jclient)
    CP.update_resource_based_policy(bucket_name,config['accounts'], config['actions'], jclient)
    CP.attach_policy_to_resource(bucket_name,resources,jclient)

def write_to_dss(account_id,directory,file_name):
    CONFIG = ConfigParser.ConfigParser()
    CONFIG.read('/etc/vpc_flow_logs.cfg')
    logs = WF.config_section_map(CONFIG, 'logs')
    secret = WF.config_section_map(CONFIG, 'secret')
    bucket = WF.config_section_map(CONFIG, 'bucket')
    bucket['actions'] = bucket['actions'].split(',')
    bucket['accounts'] = account_id[20:]
    bucket['resources'] = [json.loads(resource) for resource in bucket['resources'].split(',')]
    bucket_name=directory
    jclient = initiate_client(secret)

    policy_update(bucket,secret,bucket_name,jclient,logs['dss_account_id'])
    put_logs(directory,bucket_name,jclient,file_name)
    

def get_logs(account_id):

    end_time= datetime.datetime.now()
    start_time= end_time - datetime.timedelta(minutes = 40)
    directory= 'vpc-flow-log-'+account_id[20:]
    file_name= directory+'-'+start_time.strftime('%d_%m_%Y-%H_%M')
    start_time= start_time.strftime('%d-%m-%Y %H:%M:%S')
    end_time= end_time.strftime('%d-%m-%Y %H:%M:%S')
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(directory+'/'+file_name, 'a') as outfile:
        outfile.write('{ "log_data" : [')
    if WF.get_log_in_time(start_time,end_time,directory,file_name,account_id,0,'destvn'):
        with open(directory+'/'+file_name, 'a') as outfile:
            outfile.write(',')
    WF.get_log_in_time(start_time,end_time,directory,file_name,account_id,1,'sourcevn')
    with open(directory+'/'+file_name, 'a') as outfile:
        outfile.write(']}')
    
    write_to_dss(account_id,directory,file_name)

def get_log_enable_account_ids():

    CONFIG = ConfigParser.ConfigParser()
    CONFIG.read('/etc/vpc_flow_logs.cfg')
    secret = WF.config_section_map(CONFIG, 'secret')
    jclient = initiate_client(secret)
    res = jclient.vpc.describe_flow_log_enable_accounts('describe-flow-log-enable-accounts')
    return res['DescribeFlowLogEnableAccountsResponse']['accountIds']['item']
