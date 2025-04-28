# test_edit_reminder.py
import unittest
import os
import json
import boto3
from moto import mock_dynamodb
from botocore.exceptions import ClientError
from ..edit import edit_reminder

class TestEditReminder(unittest.TestCase):
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
    self.test_reminder = {
      'userId': 'test-user',
      'reminderId': '123',
      'title': 'Original Title',
      'description': 'Original Description',
      'triggerAt': '2023-01-01T00:00:00Z',
      'status': 'pending'
    }
    self.table.put_item(Item=self.test_reminder)
    
    # Mock event base
    self.base_event = {
      'requestContext': {
          'authorizer': {
              'claims': {
                  'userId': 'test-user'
              }
          }
      },
      'pathParameters': {
          'id': '123'
      },
      'body': json.dumps({})
    }

  def tearDown(self):
    # Limpiar mocks
    self.dynamodb = None
    self.table = None

  def test_edit_title_successfully(self):
    # Configurar evento
    event = self.base_event.copy()
    event['body'] = json.dumps({'title': 'New Title'})
    
    # Ejecutar función
    response = edit_reminder(event, None)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 200)
    response_body = json.loads(response['body'])
    self.assertEqual(response_body['title'], 'New Title')
    self.assertEqual(response_body['description'], 'Original Description')
    
    # Verificar que se actualizó en DynamoDB
    item = self.table.get_item(
      Key={'userId': 'test-user', 'reminderId': '123'}
    ).get('Item')
    self.assertEqual(item['title'], 'New Title')

  def test_edit_multiple_fields(self):
    # Configurar evento
    event = self.base_event.copy()
    event['body'] = json.dumps({
      'title': 'New Title',
      'description': 'New Description',
      'triggerAt': '2023-12-31T00:00:00Z'
    })
    
    # Ejecutar función
    response = edit_reminder(event, None)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 200)
    response_body = json.loads(response['body'])
    self.assertEqual(response_body['title'], 'New Title')
    self.assertEqual(response_body['description'], 'New Description')
    self.assertEqual(response_body['triggerAt'], '2023-12-31T00:00:00Z')

  def test_no_fields_to_update(self):
    # Configurar evento
    event = self.base_event.copy()
    event['body'] = json.dumps({})
    
    # Ejecutar función
    response = edit_reminder(event, None)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 400)
    response_body = json.loads(response['body'])
    self.assertEqual(response_body['error'], 'No fields to update')

  def test_edit_non_existent_reminder(self):
    # Configurar evento
    event = self.base_event.copy()
    event['pathParameters']['id'] = 'non-existent'
    event['body'] = json.dumps({'title': 'New Title'})
    
    # Ejecutar función
    response = edit_reminder(event, None)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 500)
    response_body = json.loads(response['body'])
    self.assertEqual(response_body['error'], 'Could not edit reminder')

  def test_edit_other_users_reminder(self):
    # Configurar evento
    event = self.base_event.copy()
    event['requestContext']['authorizer']['claims']['userId'] = 'other-user'
    event['body'] = json.dumps({'title': 'New Title'})
    
    # Ejecutar función
    response = edit_reminder(event, None)
    
    # Verificar respuesta
    self.assertEqual(response['statusCode'], 500)
    response_body = json.loads(response['body'])
    self.assertEqual(response_body['error'], 'Could not edit reminder')

  def test_offline_mode(self):
    # Configurar entorno offline
    os.environ['IF_OFFLINE'] = 'true'
    
    # Configurar evento
    event = self.base_event.copy()
    event['body'] = json.dumps({'title': 'Offline Title'})
    
    # Ejecutar función
    response = edit_reminder(event, None)
    
    # Verificar que intentó usar DynamoDB local
    self.assertEqual(response['statusCode'], 500)  # Fallará porque no hay DynamoDB local

  def test_dynamodb_error(self):
    # Simular error de DynamoDB
    with unittest.mock.patch('boto3.resource') as mock_resource:
      mock_table = unittest.mock.MagicMock()
      mock_table.update_item.side_effect = ClientError(
        {'Error': {'Code': '500', 'Message': 'Internal Server Error'}}, 
        'UpdateItem'
      )
      mock_resource.return_value.Table.return_value = mock_table
      
      # Configurar evento
      event = self.base_event.copy()
      event['body'] = json.dumps({'title': 'Error Title'})
      
      # Ejecutar función
      response = edit_reminder(event, None)
      
      # Verificar respuesta
      self.assertEqual(response['statusCode'], 500)
      response_body = json.loads(response['body'])
      self.assertEqual(response_body['error'], 'Could not edit reminder')

if __name__ == '__main__':
    unittest.main()