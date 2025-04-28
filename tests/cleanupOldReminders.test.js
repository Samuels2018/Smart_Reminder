// cleanupOldReminders.test.js
const { cleanupOldReminders } = require('../cleanup/cleanupOldReminders');
const { DynamoDBDocumentClient, ScanCommand, BatchWriteCommand } = require('@aws-sdk/lib-dynamodb');
const { mockClient } = require('aws-sdk-client-mock');
const ddbMock = mockClient(DynamoDBDocumentClient);

// Mock para console.error
console.error = jest.fn();

beforeEach(() => {
  ddbMock.reset();
  process.env.DB_TABLE = 'test-table';
});

describe('cleanupOldReminders', () => {
  it('should return 200 and count of deleted items when cleanup is successful', async () => {
    // Mockear el primer scan que devuelve items
    ddbMock.on(ScanCommand).resolvesOnce({
      Items: [
        { userId: 'user1', reminderId: 'rem1' },
        { userId: 'user1', reminderId: 'rem2' }
      ],
      LastEvaluatedKey: { userId: 'user1', reminderId: 'rem2' }
    })
    // Mockear el segundo scan (paginación) que devuelve más items
    .resolvesOnce({
      Items: [
        { userId: 'user2', reminderId: 'rem3' }
      ]
    })
    // Mockear batchWrite
    .on(BatchWriteCommand).resolves({});

    const result = await cleanupOldReminders({});

    expect(result.statusCode).toBe(200);
    expect(result.body).toBe('Recordatorios eliminados: 3');
    expect(ddbMock.calls()).toHaveLength(3); // 2 scans + 1 batchWrite
  });

  it('should handle empty results and return 200 with 0 deletions', async () => {
    ddbMock.on(ScanCommand).resolvesOnce({ Items: [] });
    
    const result = await cleanupOldReminders({});
    
    expect(result.statusCode).toBe(200);
    expect(result.body).toBe('Recordatorios eliminados: 0');
    expect(ddbMock.calls()).toHaveLength(1); // Solo un scan
  });

  it('should correctly batch items in groups of 25', async () => {
    // Crear 30 items de prueba
    const mockItems = Array.from({ length: 30 }, (_, i) => ({
      userId: `user${Math.floor(i / 10)}`,
      reminderId: `rem${i}`
    }));

    ddbMock.on(ScanCommand).resolvesOnce({
      Items: mockItems
    });

    const batchWriteCalls = [];
    ddbMock.on(BatchWriteCommand).callsFake(input => {
      batchWriteCalls.push(input);
      return {};
    });

    await cleanupOldReminders({});

    expect(batchWriteCalls).toHaveLength(2); // 25 + 5
    expect(batchWriteCalls[0].RequestItems['test-table']).toHaveLength(25);
    expect(batchWriteCalls[1].RequestItems['test-table']).toHaveLength(5);
  });

  it('should handle pagination in scan results', async () => {
    ddbMock.on(ScanCommand)
      .resolvesOnce({
        Items: Array.from({ length: 10 }, (_, i) => ({
          userId: 'user1',
          reminderId: `rem${i}`
        })),
        LastEvaluatedKey: { userId: 'user1', reminderId: 'rem9' }
      })
      .resolvesOnce({
        Items: Array.from({ length: 5 }, (_, i) => ({
          userId: 'user2',
          reminderId: `rem${i + 10}`
        }))
      })
      .on(BatchWriteCommand).resolves({});

    const result = await cleanupOldReminders({});

    expect(result.body).toBe('Recordatorios eliminados: 15');
    expect(ddbMock.calls(ScanCommand)).toHaveLength(2);
  });

  it('should return 500 and log error when DynamoDB scan fails', async () => {
    ddbMock.on(ScanCommand).rejects(new Error('DB error'));

    const result = await cleanupOldReminders({});

    expect(result.statusCode).toBe(500);
    expect(JSON.parse(result.body)).toEqual({ message: 'Internal server error' });
    expect(console.error).toHaveBeenCalled();
  });

  it('should return 500 and log error when DynamoDB batchWrite fails', async () => {
    ddbMock.on(ScanCommand).resolvesOnce({
      Items: [
        { userId: 'user1', reminderId: 'rem1' }
      ]
    });
    ddbMock.on(BatchWriteCommand).rejects(new Error('Batch write failed'));

    const result = await cleanupOldReminders({});

    expect(result.statusCode).toBe(500);
    expect(console.error).toHaveBeenCalled();
  });

  it('should use correct filter expression and attributes', async () => {
    const now = Date.now();
    const thirtyDaysAgo = now - (30 * 24 * 60 * 60 * 1000);

    ddbMock.on(ScanCommand).resolvesOnce({ Items: [] });

    await cleanupOldReminders({});

    const scanCommand = ddbMock.calls(ScanCommand)[0].args[0].input;
    expect(scanCommand.TableName).toBe('test-table');
    expect(scanCommand.FilterExpression).toBe('#status = :sent AND triggerAt <= :oldDate');
    expect(scanCommand.ExpressionAttributeNames).toEqual({
      '#status': 'status'
    });
    expect(scanCommand.ExpressionAttributeValues).toEqual({
      ':sent': 'sent',
      ':oldDate': thirtyDaysAgo
    });
    expect(scanCommand.ProjectionExpression).toBe('userId, reminderId');
  });
});