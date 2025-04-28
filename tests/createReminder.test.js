// createReminder.test.js
const { createReminder } = require('../create_reminder/createReminder');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');
const { mockClient } = require('aws-sdk-client-mock');
const { v4: uuidv4 } = require('uuid');

// Mock para DynamoDB
const ddbMock = mockClient(DynamoDBDocumentClient);

// Mock para console.error y uuidv4
console.error = jest.fn();
jest.mock('uuid', () => ({
  v4: jest.fn(() => 'mocked-uuid')
}));

beforeEach(() => {
  ddbMock.reset();
  process.env.REMINDERS_TABLE = 'reminders-table';
  process.env.OFFLINE = undefined;
});

describe('createReminder', () => {
  const mockEvent = (body, claims = { userId: 'test-user' }) => ({
    body: JSON.stringify(body),
    requestContext: {
      authorizer: {
        claims
      }
    }
  });

  it('should create a reminder successfully', async () => {
    const testData = {
      tile: 'Test Reminder',
      triggerAt: '2023-12-31T00:00:00Z',
      description: 'Test description',
      notificationType: 'sms',
      metadata: { important: true }
    };

    ddbMock.on(PutCommand).resolves({});

    const result = await createReminder(mockEvent(testData));

    expect(result.statusCode).toBe(201);
    const responseBody = JSON.parse(result.body);
    
    expect(responseBody).toMatchObject({
      userId: 'test-user',
      reminderId: 'mocked-uuid',
      tile: testData.tile,
      description: testData.description,
      triggerAt: testData.triggerAt,
      status: 'pending',
      notificationType: 'sms',
      metadata: { important: true }
    });
    expect(responseBody.createdAt).toBeDefined();
    expect(responseBody.updatedAt).toBeDefined();

    // Verificar que se llamó a DynamoDB con los parámetros correctos
    const putCommand = ddbMock.calls(PutCommand)[0].args[0].input;
    expect(putCommand.TableName).toBe('reminders-table');
    expect(putCommand.Item).toEqual(responseBody);
  });

  it('should use default values for optional fields', async () => {
    const testData = {
      tile: 'Test Reminder',
      triggerAt: '2023-12-31T00:00:00Z'
    };

    ddbMock.on(PutCommand).resolves({});

    const result = await createReminder(mockEvent(testData));
    const responseBody = JSON.parse(result.body);

    expect(responseBody.description).toBe('');
    expect(responseBody.notificationType).toBe('email');
    expect(responseBody.metadata).toEqual({});
  });

  it('should return 400 when required fields are missing', async () => {
    const testCases = [
      { triggerAt: '2023-12-31T00:00:00Z' }, // missing tile
      { tile: 'Test Reminder' } // missing triggerAt
    ];

    for (const testData of testCases) {
      const result = await createReminder(mockEvent(testData));
      expect(result.statusCode).toBe(400);
      expect(JSON.parse(result.body)).toEqual({ message: 'Invalid request data' });
    }
  });

  it('should handle DynamoDB errors', async () => {
    const testData = {
      tile: 'Test Reminder',
      triggerAt: '2023-12-31T00:00:00Z'
    };

    ddbMock.on(PutCommand).rejects(new Error('DynamoDB error'));

    const result = await createReminder(mockEvent(testData));

    expect(result.statusCode).toBe(500);
    expect(JSON.parse(result.body)).toEqual({ message: 'Internal server error' });
    expect(console.error).toHaveBeenCalledWith('Error creating reminder:', expect.any(Error));
  });

  it('should configure local DynamoDB when OFFLINE is set', async () => {
    process.env.OFFLINE = 'true';
    const testData = {
      tile: 'Test Reminder',
      triggerAt: '2023-12-31T00:00:00Z'
    };

    ddbMock.on(PutCommand).resolves({});

    await createReminder(mockEvent(testData));

    // Verificar que se configuró el cliente para modo offline
    expect(AWS.config.update).toHaveBeenCalledWith({
      region: 'localhost',
      endpoint: 'http://localhost:8000'
    });
  });

  it('should use userId from authorizer claims', async () => {
    const testData = {
      tile: 'Test Reminder',
      triggerAt: '2023-12-31T00:00:00Z'
    };
    const customClaims = { userId: 'custom-user-id' };

    ddbMock.on(PutCommand).resolves({});

    const result = await createReminder(mockEvent(testData, customClaims));
    const responseBody = JSON.parse(result.body);

    expect(responseBody.userId).toBe('custom-user-id');
  });
});

// Mock para AWS.config.update
jest.mock('aws-sdk', () => {
  const originalAWS = jest.requireActual('aws-sdk');
  return {
    ...originalAWS,
    config: {
      update: jest.fn(),
      ...originalAWS.config
    },
    DynamoDB: {
      DocumentClient: jest.fn(() => ({
        put: jest.fn().mockReturnValue({
          promise: jest.fn()
        })
      }))
    }
  };
});