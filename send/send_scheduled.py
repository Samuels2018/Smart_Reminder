import boto3
import os
import json
from datetime import datetime, timezone


def send_scheduled_reminders (event, context):
  dynamodb = boto3.resource('dynamodb')
  IF_OFLINE = os.environ.get('IF_OFFLINE', 'false').lower() == 'true'
  if IF_OFLINE:
    boto3.Session(
      aws_access_key_id='fakeMyKeyId',
      aws_secret_access_key='fakeSecretAccessKey',
    )
    dynamodb = boto3.resource('dynamodb', endpoint_url='http://localhost:8000')
  table = dynamodb.Table(os.environ['REMINDERS_TABLE'])
  sns = boto3.client('sns')

  try:

    # miliseconds
    now = int(datetime.now().timestamp() * 1000)

    response = table.query(
      IndexName='TriggerTimeIndex',
      KeyConditionExpression='userId = :userId AND triggerAt <= :now',
      FilterExpression='#status = :pending',
      ExpressionAttributeNames={
        '#status': 'status'
      },
      ExpressionAttributeValues={
        ':userId': 'all',  # Escaneo global
        ':now': now,
        ':pending': 'pending'
      },
      ProjectionExpression='reminderId, userId, title, description, notificationTypes, metadata'
    )

    reminders = response.get('Items', [])

    for reminder in reminders:
      message = {
        'default': f"Recordatorio: {reminder['title']}",
        'email': f"Subject: Recordatorio\n\n{reminder['title']}\n{reminder.get('description', '')}",
        'sms': f"Recordatorio: {reminder['title']}"
      }

      sns.publish(
        TopicArn=os.environ['NOTIFICATION_TOPIC'],
        Message=json.dumps(message),
        MessageStructure='json',
        MessageAttributes={
          'userId': {
            'DataType': 'String',
            'StringValue': reminder['userId']
          },
          'notificationTypes': {
            'DataType': 'String.Array',
            'StringValue': json.dumps(reminder['notificationTypes'])
          }
        }
      )
            
      # Marcar como enviado
      table.update_item(
        Key={
          'userId': reminder['userId'],
          'reminderId': reminder['reminderId']
        },
        UpdateExpression='SET #status = :sent',
        ExpressionAttributeNames={
          '#status': 'status'
        },
        ExpressionAttributeValues={
          ':sent': 'sent'
        }
      )

    return {
      'statusCode': 200,
      'body': f"Recordatorios procesados: {len(reminders)}"
    }

  except Exception as err:
    print(f"Error sending scheduled reminders: {err}")
    return {
      'statusCode': 500,
      'body': json.dumps({
        'error': 'Could not send scheduled reminders'
      })
    }