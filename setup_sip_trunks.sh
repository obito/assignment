#!/bin/bash

# LiveKit CLI configuration
LIVEKIT_URL="http://localhost:7880"
API_KEY="API_KEY"
API_SECRET="API_SECRET"

# Your Twilio details
PHONE_NUMBER="+13208185352"
SIP_DOMAIN="my-test-cozmox.pstn.twilio.com"

echo "🎯 Setting up SIP trunks for self-hosted LiveKit"
echo "=================================================="

# Get Twilio credentials
echo "Enter your Twilio SIP trunk username:"
read TWILIO_USERNAME
echo "Enter your Twilio SIP trunk password:"
read -s TWILIO_PASSWORD

echo ""
echo "📞 Creating Inbound Trunk..."
lk --url $LIVEKIT_URL --api-key $API_KEY --api-secret $API_SECRET sip inbound create \
  --name "My inbound trunk" \
  --numbers $PHONE_NUMBER

echo ""
echo "📞 Creating Outbound Trunk..."
lk --url $LIVEKIT_URL --api-key $API_KEY --api-secret $API_SECRET sip outbound create \
  --name "My outbound trunk" \
  --address $SIP_DOMAIN \
  --numbers $PHONE_NUMBER \
  --auth-user $TWILIO_USERNAME \
  --auth-pass $TWILIO_PASSWORD

echo ""
echo "📋 Creating Dispatch Rule..."
lk --url $LIVEKIT_URL --api-key $API_KEY --api-secret $API_SECRET sip dispatch create \
  --name "My dispatch rule" \
  --individual "call-"

echo ""
echo "🎉 SIP Setup Complete!"
echo "======================"
echo "📱 Phone Number: $PHONE_NUMBER"
echo "📞 SIP Domain: $SIP_DOMAIN"
echo ""
echo "💡 Next step: Add the outbound trunk ID to your agent code!"
echo "   Run: lk --url $LIVEKIT_URL --api-key $API_KEY --api-secret $API_SECRET sip outbound list"
