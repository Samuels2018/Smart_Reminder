import os
import json
import boto3
from boto3.dynamodb.conditions import Key

def list_reminders(event, context):
  dynamodb = boto3.resource('dynamodb')
  IF_OFLINE = os.environ.get('IF_OFFLINE', 'false').lower() == 'true'
  if IF_OFLINE:
    boto3.Session(
      aws_access_key_id='fakeMyKeyId',
      aws_secret_access_key='fakeSecretAccessKey',
    )

    dynamodb = boto3.resource('dynamodb', endpoint_url='http://localhost:8000')

  table = dynamodb.Table(os.environ['REMINDERS_TABLE'])

  try: 

    claims = event['requestContext']['authorizer']['claims']
    user_id = claims['userId']
    
    # Opciones de consulta
    query_params = event.get('queryStringParameters', {})
    limit = int(query_params.get('limit', 10))
    next_token = query_params.get('nextToken')
    
    # Consulta a DynamoDB
    query_args = {
      'KeyConditionExpression': Key('userId').eq(user_id),
      'Limit': limit,
      'ScanIndexForward': False  # Orden descendente (más recientes primero)
    }
    
    if next_token:
        query_args['ExclusiveStartKey'] = json.loads(next_token)
        
    response = table.query(**query_args)
    
    return {
      'statusCode': 200,
      'body': json.dumps({
        'items': response['Items'],
        'nextToken': response.get('LastEvaluatedKey')
      })
    }

  except Exception as err:
    print(f"Error listing reminders: {err}")
    return {
      'statusCode': 500,
      'body': json.dumps({
        'error': 'Could not list reminders'
      })
    }
