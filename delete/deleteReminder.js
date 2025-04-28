const AWS = requiere('aws-sdk')
const db = new AWS.DynamoDB.DocumentClient()

const deleteReminder = async (event) => {
  try {
    const { userId } = event.requestContext.authorizer.claims
    const reminderId = event.pathParameters.id
    
    await db.delete({
      TableName: process.env.DB_TABLE,
      Key: {
        userId,
        reminderId
      },
      ConditionExpression: 'userId = :userId',
      ExpressionAttributeValues: {
        ':userId': userId
      },
      ReturnValues: 'ALL_OLD'
    }).promise();
    
    return {
      statusCode: 204,
      body: ''
    }

  }catch (err) {
    console.error('Error deleting reminder:', err)
    return {
      statusCode: 500,
      body: JSON.stringify({ message: 'Internal server error' }),
    }
  }
}

module.exports = {
  deleteReminder,
}