const AWS = require('aws-sdk')
const db = new AWS.DynamoDB.DocumentClient()

const cleanupOldReminders = async (event) => {
  try {
    const now = Date.now();
    const thirtyDaysAgo = now - (30 * 24 * 60 * 60 * 1000); // 30 días en milisegundos
    
    // 1. Escanear recordatorios enviados y expirados
    const params = {
      TableName: process.env.DB_TABLE,
      FilterExpression: '#status = :sent AND triggerAt <= :oldDate',
      ExpressionAttributeNames: {
        '#status': 'status'
      },
      ExpressionAttributeValues: {
        ':sent': 'sent',
        ':oldDate': thirtyDaysAgo
      },
      ProjectionExpression: 'userId, reminderId'
    };
    
    const itemsToDelete = [];
    let lastEvaluatedKey = null;
    
    do {
      if (lastEvaluatedKey) {
        params.ExclusiveStartKey = lastEvaluatedKey;
      }
      
      const result = await db.scan(params).promise();
      itemsToDelete.push(...result.Items);
      lastEvaluatedKey = result.LastEvaluatedKey;
    } while (lastEvaluatedKey);
    
    // 2. Eliminar en lotes (máximo 25 items por batch)
    const batchSize = 25;
    for (let i = 0; i < itemsToDelete.length; i += batchSize) {
      const batch = itemsToDelete.slice(i, i + batchSize);
      
      const deleteRequests = batch.map(item => ({
        DeleteRequest: {
          Key: {
            userId: item.userId,
            reminderId: item.reminderId
          }
        }
      }));
      
      await db.batchWrite({
        RequestItems: {
          [process.env.DB_TABLE]: deleteRequests
        }
      }).promise();
    }
    
    return {
      statusCode: 200,
      body: `Recordatorios eliminados: ${itemsToDelete.length}`
    };

  } catch (error) {
    console.error('Error cleaning up old reminders:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ message: 'Internal server error' }),
    };
  }
}

module.exports = {
  cleanupOldReminders,
}