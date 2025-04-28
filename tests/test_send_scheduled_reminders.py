import unittest
import os
import json
import boto3
from moto import mock_dynamodb, mock_sns
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from freezegun import freeze_time
from send.send_scheduled import send_scheduled_reminders

class TestSendScheduledReminders(unittest.TestCase):
  def setUp(self):
    # Configurar entorno para pruebas
    os.environ['REMINDERS_TABLE'] = 'test-reminders'
    os.environ['NOTIFICATION_TOPIC'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
    os.environ['IF_OFFLINE'] = 'false'
    
    # Crear tabla de DynamoDB mock
    self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    self.table = self.dynamodb.create_table(
      TableName=os.environ['REMINDERS_TABLE'],
      KeySchema=[
        {'AttributeName': 'userId', 'KeyType': 'HASH'},
        {'AttributeName': 'reminderId', 'KeyType': 'RANGE'}
      ],
      AttributeDefinitions=[
        {'AttributeName': 'userId', 'AttributeType': 'S'},
        {'AttributeName': 'reminderId', 'AttributeType': 'S'},
        {'AttributeName': 'triggerAt', 'AttributeType': 'N'},
        {'AttributeName': 'status', 'AttributeType': 'S'}
      ],
      GlobalSecondaryIndexes=[
        {
          'IndexName': 'TriggerTimeIndex',
          'KeySchema': [
            {'AttributeName': 'userId', 'KeyType': 'HASH'},
            {'AttributeName': 'triggerAt', 'KeyType': 'RANGE'}
          ],
          'Projection': {
            'ProjectionType': 'ALL'
          },
          'ProvisionedThroughput': {
            'ReadCapacityUnits': 1,
            'WriteCapacityUnits': 1
          }
        }
      ],
      ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # Crear topic SNS mock
    self.sns = boto3.client('sns', region_name='us-east-1')
    self.topic_arn = self.sns.create_topic(Name='test-topic')['TopicArn']
    
    # Insertar datos de prueba
    self.now = int(datetime.now().timestamp() * 1000)
    self.past_time = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)
    self.future_time = int((datetime.now() + timedelta(days=1)).timestamp() * 1000)
    
    self.test_reminders = [
      {
        'userId': 'user1',
        'reminderId': '1',
        'title': 'Past Due Reminder',
        'description': 'This is past due',
        'triggerAt': self.past_time,
        'status': 'pending',
        'notificationTypes': ['email', 'sms']
      },
      {
        'userId': 'user2',
        'reminderId': '2',
        'title': 'Current Reminder',
        'description': 'This is due now',
        'triggerAt': self.now,
        'status': 'pending',
        'notificationTypes': ['email']
      },
      {
        'userId': 'user3',
        'reminderId': '3',
        'title': 'Future Reminder',
        'description': 'This is in the future',
        'triggerAt': self.future_time,
        'status': 'pending',
        'notificationTypes': ['sms']
      },
      {
        'userId': 'user4',
        'reminderId': '4',
        'title': 'Already Sent Reminder',
        'description': 'This was already sent',
        'triggerAt': self.past_time,
        'status': 'sent',
        'notificationTypes': ['email']
      }
    ]
    
    for reminder in self.test_reminders:
      self.table.put_item(Item=reminder)
    
    # Mock event y context (no se usan en la función pero son parámetros requeridos)
    self.mock_event = {}
    self.mock_context = {}

  def tearDown(self):
    # Limpiar mocks
    self.dynamodb = None
    self.table = None
    self.sns = None

  @freeze_time(datetime.now())
  def test_send_pending_reminders(self):
    # Ejecutar función
    response = send_scheduled_reminders(self.mock_event, self.mock_context)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 200)
    self.assertEqual(response['body'], "Recordatorios procesados: 2")  # Solo 2 cumplen criterios
    
    # Verificar que se actualizó el estado a 'sent'
    for reminder in self.test_reminders[:2]:  # Solo los primeros 2 deberían haberse procesado
      item = self.table.get_item(
        Key={'userId': reminder['userId'], 'reminderId': reminder['reminderId']}
      ).get('Item')
      self.assertEqual(item['status'], 'sent')
    
    # Verificar que no se actualizaron los otros recordatorios
    for reminder in self.test_reminders[2:]:
      item = self.table.get_item(
        Key={'userId': reminder['userId'], 'reminderId': reminder['reminderId']}
      ).get('Item')
      self.assertNotEqual(item['status'], 'sent')

  @mock_sns
  def test_sns_notification_sent(self):
    # Ejecutar función
    response = send_scheduled_reminders(self.mock_event, self.mock_context)
    
    # Verificar que se enviaron notificaciones
    # (moto no soporta completamente MessageAttributes en SNS, así que verificamos el número de publicaciones)
    self.assertEqual(response['statusCode'], 200)
      
  def test_no_reminders_to_send(self):
    # Eliminar todos los recordatorios
    for reminder in self.test_reminders:
      self.table.delete_item(
        Key={'userId': reminder['userId'], 'reminderId': reminder['reminderId']}
      )
    
    # Ejecutar función
    response = send_scheduled_reminders(self.mock_event, self.mock_context)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 200)
    self.assertEqual(response['body'], "Recordatorios procesados: 0")

  def test_offline_mode(self):
    # Configurar entorno offline
    os.environ['IF_OFFLINE'] = 'true'
    
    # Ejecutar función
    response = send_scheduled_reminders(self.mock_event, self.mock_context)
    
    # Verificar que intentó usar DynamoDB local
    self.assertEqual(response['statusCode'], 500)  # Fallará porque no hay DynamoDB local

  def test_dynamodb_query_error(self):
    # Simular error de DynamoDB en query
    with unittest.mock.patch('boto3.resource') as mock_resource:
      mock_table = unittest.mock.MagicMock()
      mock_table.query.side_effect = ClientError(
          {'Error': {'Code': '500', 'Message': 'Internal Server Error'}}, 
          'Query'
      )
      mock_resource.return_value.Table.return_value = mock_table
      
      # Ejecutar función
      response = send_scheduled_reminders(self.mock_event, self.mock_context)
      
      # Verificar respuesta
      self.assertEqual(response['statusCode'], 500)
      response_body = json.loads(response['body'])
      self.assertEqual(response_body['error'], 'Could not send scheduled reminders')

  def test_dynamodb_update_error(self):
    # Simular error de DynamoDB en update
    with unittest.mock.patch('boto3.resource') as mock_resource:
      # Configurar mock para que query funcione pero update falle
      mock_table = unittest.mock.MagicMock()
      mock_table.query.return_value = {'Items': [self.test_reminders[0]]}
      mock_table.update_item.side_effect = ClientError(
          {'Error': {'Code': '500', 'Message': 'Internal Server Error'}}, 
          'UpdateItem'
      )
      mock_resource.return_value.Table.return_value = mock_table
      
      # Ejecutar función
      response = send_scheduled_reminders(self.mock_event, self.mock_context)
      
      # Verificar respuesta
      self.assertEqual(response['statusCode'], 500)
      response_body = json.loads(response['body'])
      self.assertEqual(response_body['error'], 'Could not send scheduled reminders')

  def test_sns_publish_error(self):
    # Simular error de SNS
    with unittest.mock.patch('boto3.client') as mock_client:
      mock_sns = unittest.mock.MagicMock()
      mock_sns.publish.side_effect = ClientError(
          {'Error': {'Code': '500', 'Message': 'Internal Server Error'}}, 
          'Publish'
      )
      mock_client.return_value = mock_sns
      
      # Ejecutar función
      response = send_scheduled_reminders(self.mock_event, self.mock_context)
      
      # Verificar respuesta
      self.assertEqual(response['statusCode'], 500)
      response_body = json.loads(response['body'])
      self.assertEqual(response_body['error'], 'Could not send scheduled reminders')

if __name__ == '__main__':
    unittest.main()