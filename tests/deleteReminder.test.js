// deleteReminder.test.js
const { deleteReminder } = require('../delete/deleteReminder');
const { DynamoDBDocumentClient, DeleteCommand } = require('@aws-sdk/lib-dynamodb');
const { mockClient } = require('aws-sdk-client-mock');

// Mock para DynamoDB
const ddbMock = mockClient(DynamoDBDocumentClient);

// Mock para console.error
console.error = jest.fn();

beforeEach(() => {
  ddbMock.reset();
  process.env.DB_TABLE = 'reminders-table';
});

describe('deleteReminder', () => {
  const mockEvent = (reminderId, userId = 'test-user') => ({
    pathParameters: { id: reminderId },
    requestContext: {
      authorizer: {
        claims: { userId }
      }
    }
  });

  it('should delete a reminder successfully', async () => {
    const testReminderId = '12345';
    const testUserId = 'user-1';
    
    ddbMock.on(DeleteCommand).resolves({
      Attributes: {
        userId: testUserId,
        reminderId: testReminderId,
        tile: 'Test Reminder'
      }
    });

    const result = await deleteReminder(mockEvent(testReminderId, testUserId));

    expect(result.statusCode).toBe(204);
    expect(result.body).toBe('');

    // Verificar que se llamó a DynamoDB con los parámetros correctos
    const deleteCommand = ddbMock.calls(DeleteCommand)[0].args[0].input;
    expect(deleteCommand.TableName).toBe('reminders-table');
    expect(deleteCommand.Key).toEqual({
      userId: testUserId,
      reminderId: testReminderId
    });
    expect(deleteCommand.ConditionExpression).toBe('userId = :userId');
    expect(deleteCommand.ExpressionAttributeValues).toEqual({
      ':userId': testUserId
    });
    expect(deleteCommand.ReturnValues).toBe('ALL_OLD');
  });

  it('should return 500 when DynamoDB fails', async () => {
    const testReminderId = '12345';
    
    ddbMock.on(DeleteCommand).rejects(new Error('DynamoDB error'));

    const result = await deleteReminder(mockEvent(testReminderId));

    expect(result.statusCode).toBe(500);
    expect(JSON.parse(result.body)).toEqual({ message: 'Internal server error' });
    expect(console.error).toHaveBeenCalledWith('Error deleting reminder:', expect.any(Error));
  });

  it('should return 404 when reminder does not exist', async () => {
    const testReminderId = 'non-existent';
    const testUserId = 'user-1';
    
    ddbMock.on(DeleteCommand).rejects({
      name: 'ConditionalCheckFailedException',
      message: 'The conditional request failed'
    });

    const result = await deleteReminder(mockEvent(testReminderId, testUserId));

    expect(result.statusCode).toBe(404);
    expect(JSON.parse(result.body)).toEqual({ error: 'Recordatorio no encontrado' });
  });

  it('should return 404 when trying to delete other user reminder', async () => {
    const testReminderId = '12345';
    const ownerUserId = 'user-1';
    const requestingUserId = 'user-2';
    
    ddbMock.on(DeleteCommand).rejects({
      name: 'ConditionalCheckFailedException',
      message: 'The conditional request failed'
    });

    const result = await deleteReminder(mockEvent(testReminderId, requestingUserId));

    expect(result.statusCode).toBe(404);
    expect(JSON.parse(result.body)).toEqual({ error: 'Recordatorio no encontrado' });
  });

  it('should use userId from authorizer claims', async () => {
    const testReminderId = '12345';
    const testUserId = 'custom-user-id';
    
    ddbMock.on(DeleteCommand).resolves({
      Attributes: {
        userId: testUserId,
        reminderId: testReminderId
      }
    });

    await deleteReminder(mockEvent(testReminderId, testUserId));

    const deleteCommand = ddbMock.calls(DeleteCommand)[0].args[0].input;
    expect(deleteCommand.Key.userId).toBe(testUserId);
    expect(deleteCommand.ExpressionAttributeValues[':userId']).toBe(testUserId);
  });
});