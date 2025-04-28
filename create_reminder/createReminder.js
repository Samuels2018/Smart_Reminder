const AWS = require('aws-sdk')
const { v4: uuidv4 } = require('uuid')
const sendNotification = require('../helpers/notification')

const createReminder = async (event) => {
  const db = new AWS.DynamoDB.DocumentClient()

  OFFLINE = process.env.OFFLINE
  if (OFFLINE) {
    AWS.config.update({
      region: 'localhost',
      endpoint: 'http://localhost:8000'
    })
  }


  try{
    const {userId} = event.requestContext.authorizer.claims
    const data  = JSON.parse(event.body)

    if (!data.tile || !data.triggerAt) {
      return {
        statusCode: 400,
        body: JSON.stringify({ message: 'Invalid request data' }),
      }
    }

    const params = {
      userId: userId,
      reminderId: uuidv4(),
      tile: data.tile,
      description: data.description || '',
      triggerAt: data.triggerAt,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'pending',
      notificationType: data.notificationType || 'email',
      metadata: data.metadata || {},
    }

    await db.put({
      TableName: process.env.REMINDERS_TABLE,
      Item: params,
    }).promise()

    return {
      statusCode: 201,
      body: JSON.stringify(params),
    }

  }catch (error) {
    console.error('Error creating reminder:', error)
    return {
      statusCode: 500,
      body: JSON.stringify({ message: 'Internal server error' }),
    }
  }
}

module.exports = {
  createReminder,
}