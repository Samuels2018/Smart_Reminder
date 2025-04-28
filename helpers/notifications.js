const AWS = require('aws-sdk');
const ses = new AWS.SES();
const sns = new AWS.SNS();

async function sendEmail(to, subject, body) {
  const params = {
    Source: process.env.EMAIL_SENDER,
    Destination: { ToAddresses: [to] },
    Message: {
      Subject: { Data: subject },
      Body: { Text: { Data: body } }
    }
  };
  
  return ses.sendEmail(params).promise();
}

async function sendSMS(phoneNumber, message) {
  const params = {
    PhoneNumber: phoneNumber,
    Message: message
  };
  
  return sns.publish(params).promise();
}

async function sendPushNotification(userId, message) {
  const params = {
    Message: JSON.stringify(message),
    TargetArn: process.env.PUSH_NOTIFICATION_ARN,
    MessageStructure: 'json'
  };
  
  return sns.publish(params).promise();
}

module.exports = {
  sendEmail,
  sendSMS,
  sendPushNotification,
  sendNotification: async (userId, type, content) => {
    switch (type) {
      case 'email':
        return sendEmail(content.to, content.subject, content.body);
      case 'sms':
        return sendSMS(content.phoneNumber, content.message);
      case 'push':
        return sendPushNotification(userId, content);
      default:
        throw new Error(`Tipo de notificación no soportado: ${type}`);
    }
  }
};