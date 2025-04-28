# test_list_reminders.py
import unittest
import os
import json
import boto3
from botocore.exceptions import ClientError
from list import list_reminders

class TestListReminders(unittest.TestCase):
  def setUp(self):
    # Configurar entorno para pruebas
    os.environ['REMINDERS_TABLE'] = 'test-reminders'
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
          {'AttributeName': 'reminderId', 'AttributeType': 'S'}
      ],
      ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # Insertar datos de prueba
    self.test_user_id = 'test-user'
    self.test_reminders = [
      {
        'userId': self.test_user_id,
        'reminderId': '1',
        'title': 'First Reminder',
        'triggerAt': '2023-01-01T00:00:00Z'
      },
      {
        'userId': self.test_user_id,
        'reminderId': '2',
        'title': 'Second Reminder',
        'triggerAt': '2023-01-02T00:00:00Z'
      },
      {
        'userId': 'other-user',
        'reminderId': '3',
        'title': 'Other User Reminder',
        'triggerAt': '2023-01-03T00:00:00Z'
      }
    ]
    
    for reminder in self.test_reminders:
      self.table.put_item(Item=reminder)
    
    # Mock event base
    self.base_event = {
      'requestContext': {
        'authorizer': {
          'claims': {
            'userId': self.test_user_id
          }
        }
      },
      'queryStringParameters': {}
    }

  def tearDown(self):
    # Limpiar mocks
    self.dynamodb = None
    self.table = None

  def test_list_reminders_successfully(self):
    # Ejecutar función
    response = list_reminders(self.base_event, None)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 200)
    response_body = json.loads(response['body'])
    
    # Debería devolver solo los recordatorios del usuario de prueba
    self.assertEqual(len(response_body['items']), 2)
    self.assertEqual(response_body['items'][0]['reminderId'], '2')  # Orden descendente
    self.assertEqual(response_body['items'][1]['reminderId'], '1')
    self.assertIsNone(response_body.get('nextToken'))

  def test_list_with_limit(self):
    # Configurar evento con limit
    event = self.base_event.copy()
    event['queryStringParameters'] = {'limit': '1'}
    
    # Ejecutar función
    response = list_reminders(event, None)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 200)
    response_body = json.loads(response['body'])
    
    self.assertEqual(len(response_body['items']), 1)
    self.assertIsNotNone(response_body.get('nextToken'))

  def test_list_with_pagination(self):
    # Primera página (limit 1)
    event = self.base_event.copy()
    event['queryStringParameters'] = {'limit': '1'}
    first_page = list_reminders(event, None)
    first_page_body = json.loads(first_page['body'])
    
    # Segunda página (usando nextToken)
    event['queryStringParameters'] = {
      'limit': '1',
      'nextToken': first_page_body['nextToken']
    }
    second_page = list_reminders(event, None)
    second_page_body = json.loads(second_page['body'])
    
    # Verificar que tenemos todos los items
    self.assertEqual(len(first_page_body['items']), 1)
    self.assertEqual(len(second_page_body['items']), 1)
    self.assertIsNone(second_page_body.get('nextToken'))
    
    # Verificar que son diferentes items
    self.assertNotEqual(
      first_page_body['items'][0]['reminderId'],
      second_page_body['items'][0]['reminderId']
    )

  def test_empty_list(self):
    # Usuario sin recordatorios
    event = self.base_event.copy()
    event['requestContext']['authorizer']['claims']['userId'] = 'empty-user'
    
    # Ejecutar función
    response = list_reminders(event, None)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 200)
    response_body = json.loads(response['body'])
    self.assertEqual(len(response_body['items']), 0)
    self.assertIsNone(response_body.get('nextToken'))

  def test_offline_mode(self):
    # Configurar entorno offline
    os.environ['IF_OFFLINE'] = 'true'
    
    # Ejecutar función
    response = list_reminders(self.base_event, None)
    
    # Verificar que intentó usar DynamoDB local
    self.assertEqual(response['statusCode'], 500)  # Fallará porque no hay DynamoDB local

  def test_dynamodb_error(self):
    # Simular error de DynamoDB
    with unittest.mock.patch('boto3.resource') as mock_resource:
      mock_table = unittest.mock.MagicMock()
      mock_table.query.side_effect = ClientError(
        {'Error': {'Code': '500', 'Message': 'Internal Server Error'}}, 
        'Query'
      )
      mock_resource.return_value.Table.return_value = mock_table
      
      # Ejecutar función
      response = list_reminders(self.base_event, None)
      
      # Verificar respuesta
      self.assertEqual(response['statusCode'], 500)
      response_body = json.loads(response['body'])
      self.assertEqual(response_body['error'], 'Could not list reminders')

  def test_invalid_limit_parameter(self):
    # Configurar evento con limit inválido
    event = self.base_event.copy()
    event['queryStringParameters'] = {'limit': 'not-a-number'}
    
    # Ejecutar función
    response = list_reminders(event, None)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 500)
    response_body = json.loads(response['body'])
    self.assertEqual(response_body['error'], 'Could not list reminders')

  def test_invalid_next_token(self):
    # Configurar evento con nextToken inválido
    event = self.base_event.copy()
    event['queryStringParameters'] = {'nextToken': 'not-valid-json'}
    
    # Ejecutar función
    response = list_reminders(event, None)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 500)
    response_body = json.loads(response['body'])
    self.assertEqual(response_body['error'], 'Could not list reminders')

if __name__ == '__main__':
  unittest.main()