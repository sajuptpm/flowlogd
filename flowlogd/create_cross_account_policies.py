from jcsclient import client
import sys
import os
#from vpctools import vpc_functions as VF
import logging
### Usage info
### This file is helpful in creating a new bucket and giving it cross account permission
### In order to get_account_id() to work make sure you have atleast on account


LOG_FILENAME = '/var/log/flowlogd/flowlog.log'
logging.basicConfig(filename=LOG_FILENAME,
                        level=logging.DEBUG,
                        )

def create_resource_based_policy(name,accounts, actions, jclient):
    policy_document = '{\"name\": \"'+name+'\",\"statement\": [{\"action\": ['
    for action in actions :
        policy_document = policy_document +'\"'+action+ '\" , '
    policy_document = policy_document + '], \"principle\": ['


    for account in accounts:
        policy_document = policy_document + '\"jrn:jcs:iam:'+account+':User:*\",'

    policy_document = policy_document+'], \"effect\": \"allow\"}]}'

    logging.info( jclient.iam.create_resource_based_policy(policy_document = policy_document))


def update_resource_based_policy(name,accounts, actions, jclient):
    policy_document = '{\"name\": \"'+name+'\",\"statement\": [{\"action\": ['
    for action in actions :
        policy_document = policy_document +'\"'+action+ '\",'
    policy_document = policy_document[:-1] + '], \"principle\": ['


    policy_document = policy_document + '\"jrn:jcs:iam:'+accounts+':User:*\",'

    policy_document = policy_document[:-1]+'], \"effect\": \"allow\"}]}'


    logging.info( policy_document)
    logging.info( jclient.iam.update_resource_based_policy(policy_document = policy_document, name=name))




def attach_policy_to_resource(name,resources,jclient):

    resource_stat = '{\"resource\":['

    for resource in resources:
        resource_stat = resource_stat + '\"jrn:jcs:' + resource['service'] +':' + resource['account_id']+':'+ resource['resource']+'\",'

    resource_stat = resource_stat[:-1] + ']}'

    logging.info( resource_stat)
    logging.info(jclient.iam.attach_policy_to_resource(policy_name=name,resource=resource_stat))



