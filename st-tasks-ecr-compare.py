import argparse
import datetime
import logging
import sys
import boto3
import pprint
import pytz

def init():
    """Initialize system."""

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
def describe_repositories(client):
    paginator = client.get_paginator('describe_repositories')
    page_iterator = paginator.paginate()
    repositories = []
    repositoryNames = set()
    for page in page_iterator:
        repositories.extend(page['repositories'])
    
    for repo in repositories:
        repositoryNames.add(repo['repositoryName'])
    
    return repositoryNames

def find_images_ecr(ecr_client, task_images):
    logging.info('Checking if Images referenced exist in ECR ...')
    images = []
    for task_image in task_images:
        images = []
        dns = task_image.split('/')[0]
        if "amazonaws.com" in dns:
            repository_plus_image = task_image.split('/')[1]
            image_id = repository_plus_image.split(':')[1]
            repository_name = repository_plus_image.split(':')[0]
            
            paginator = ecr_client.get_paginator('list_images')
            page_iterator = paginator.paginate(repositoryName=repository_name, filter={'tagStatus': 'TAGGED'})
            for page in page_iterator:
                for i in range(len(page['imageIds'])):
                    images.append(page['imageIds'][i]['imageTag'])
            if(image_id in images):
                print ("Container image %s is in use by Service %s" % (image_id, repository_name))
        else:
            print ("%s not in ECR" % task_image)

def list_tasks(ecs_client, cluster):
    logging.info('Getting Tasks from ECS Cluster')
    paginator = ecs_client.get_paginator('list_tasks')
    page_iterator = paginator.paginate(cluster=cluster)
    task_arns = []
    tasks = []
    for page in page_iterator:
        task_arns.extend(page['taskArns'])
    tasks = [task_arn.split('/',1)[1] for task_arn in task_arns]
    return tasks

def list_task_definitions(ecs_client, tasks, cluster):
    logging.info('Getting Task Definitions from Tasks ...')
    task_definitions = list()
    for task in tasks:
        response = ecs_client.describe_tasks(
            cluster = cluster,
            tasks = [
                task,
            ]
        )
        task_definition = response['tasks'][0]['taskDefinitionArn']
        task_definitions.append(task_definition.split('/')[1])

    return task_definitions

def list_ecr_container_images(ecs_client, task_definitions):
    logging.info('Getting images from Task Definitions ...')
    images = []
    for task_definition in task_definitions:
        response = ecs_client.describe_task_definition(
            taskDefinition=task_definition,
        )
        images.append(response['taskDefinition']['containerDefinitions'][0]['image'])
    return images

def doit():
    init()
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--account', help='AWS Account Number', required=False)
    parser.add_argument('-c', '--cluster',
                        help='Cluster to run the script against',
                        required=True)
    parser.add_argument('-r', '--region', help='AWS Region', required=True)
    args = parser.parse_args()

    ecr_client = boto3.client('ecr', region_name=args.region)
    ecs_client = boto3.client('ecs', region_name=args.region)

    tasks = list_tasks(ecs_client, args.cluster)
    task_definitions = list_task_definitions(ecs_client, tasks, args.cluster)
    task_images = list_ecr_container_images(ecs_client, task_definitions)
    find_images_ecr(ecr_client, task_images)

if __name__ == '__main__':
    try:
        doit()
    except Exception as exception:  # pylint: disable=w0703
        logging.error('Error:', exc_info=True)
        sys.exit(1)