# CrowdVote Production Environment Variables

When deploying to production (Railway), set these environment variables:

## Required Django Settings
```
DEBUG=False
SECRET_KEY=your-super-secret-production-key-here
ALLOWED_HOSTS=yourdomain.com,.railway.app
```

## Database
Railway provides this automatically:
```
DATABASE_URL=postgresql://user:password@host:port/database
```

## Email Configuration

### SendPulse (Current Setup - 15,000 emails/month free, perfect for beta)
```
SENDPULSE_API_ID=your-sendpulse-api-id
SENDPULSE_API_SECRET=your-sendpulse-api-secret
SENDPULSE_FROM_NAME=CrowdVote
DEFAULT_FROM_EMAIL=noreply@crowdvote.com
```

To get your SendPulse credentials:
1. Log into your SendPulse account
2. Go to Account Settings > API tab  
3. Copy your ID and Secret values

### Future Scaling Options

When ready to handle more than 100 emails/day:

**Mailgun ($35/month)**
```
EMAIL_HOST=smtp.mailgun.org
EMAIL_HOST_USER=your-mailgun-smtp-username
EMAIL_HOST_PASSWORD=your-mailgun-smtp-password
```

**Amazon SES (Most cost-effective - $0.10/1000 emails)**
```
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_HOST_USER=your-aws-ses-access-key-id
EMAIL_HOST_PASSWORD=your-aws-ses-secret-access-key
```

## Quick Setup Guide

1. **For Mailgun**: Sign up at mailgun.com, verify domain, get SMTP credentials
2. **For SendGrid**: Sign up at sendgrid.com, create API key, use 'apikey' as username
3. **For Amazon SES**: Set up AWS account, verify domain in SES, create SMTP credentials

## Magic Link Configuration

Magic links are automatically configured to use `crowdvote.com` in production and `localhost:8000` in development. No additional configuration needed.

## Testing Email in Production

Once configured, magic links will be sent to real email addresses instead of console output.
