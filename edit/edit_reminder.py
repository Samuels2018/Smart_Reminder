import os
import json
import boto3
from boto3.dynamodb.conditions import Key

def edit_reminder (event, context):
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
    reminder_id = event['pathParameters']['id']
    
    body = json.loads(event['body'])

    update_expression = {}
    expression_value = {}
    expression_name = {}

    if 'title' in body:
      update_expression['#title'] = body['title']
      expression_value[':title'] = body['title']
      expression_name['#title'] = 'title'


    if 'description' in body:
      update_expression['#description'] = body['description']
      expression_value[':description'] = body['description']
      expression_name['#description'] = 'description'

    if 'triggerAt' in body:
      update_expression['#triggerAt'] = body['triggerAt']
      expression_value[':triggerAt'] = body['triggerAt']
      expression_name['#triggerAt'] = 'triggerAt'

    if not update_expression:
      return {
        'statusCode': 400,
        'body': json.dumps({
          'error': 'No fields to update'
        })
      }
    

    response = table.update_item(
      Key={
        'userId': user_id,
        'reminderId': reminder_id
      },
      UpdateExpression='SET ' + ', '.join([f'{k} = {v}' for k, v in update_expression.items()]),
      ExpressionAttributeValues=expression_value,
      ExpressionAttributeNames=expression_name,
      ConditionExpression=Attr('userId').eq(user_id),
      ReturnValues='ALL_NEW'
    )

    return {
      'statusCode': 200,
      'body': json.dumps(response['Attributes'])
    }

  except Exception as err:
    print(f"Error editing reminder: {err}")
    return {
      'statusCode': 500,
      'body': json.dumps({
        'error': 'Could not edit reminder'
      })
    }