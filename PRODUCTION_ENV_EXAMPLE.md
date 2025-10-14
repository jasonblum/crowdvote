# CrowdVote Production Environment Variables

Complete guide for deploying CrowdVote to Railway with environment variables.

## Railway Setup Overview

You'll create **two services** in Railway:
1. **Main web service** - Your Django app (runs 24/7)
2. **Cron service** - Weekly demo reset (runs Sunday midnight)

Both services share most environment variables.

---

## Required Variables (Both Services)

### Django Core Settings
```bash
DEBUG=False
SECRET_KEY=<generate-with-command-below>
```

**Generate SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Railway-Safe Format**: Letters, numbers, hyphens, underscores only. Avoid `#`, `@`, `!` (Railway may truncate).

### Database
```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

**Setup in Railway:**
1. Add PostgreSQL database to your project
2. Railway automatically creates `DATABASE_URL` variable
3. Reference this variable from both services:
   - Main service: Use directly
   - Cron service: Settings → Variables → "Reference" → Select `DATABASE_URL` from main service

---

## Recommended Variables

### Security & Access
```bash
ALLOWED_HOSTS=.railway.app,crowdvote.com,www.crowdvote.com
ADMIN_URL=zanzibar
ANONYMITY_SALT=<generate-unique-random-string>
```

**ALLOWED_HOSTS**: Comma-separated list of domains allowed to serve the app.
**ADMIN_URL**: Access Django admin at `https://yoursite.com/zanzibar/` instead of `/admin/` (security through obscurity).
**ANONYMITY_SALT**: Used to hash usernames in anonymous ballots. Generate a long random string.

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

---

## Railway Cron Service Setup (Weekly Demo Reset)

For the demo site to auto-reset every Sunday at midnight UTC.

### 1. Create Cron Service

In Railway dashboard:
1. **+ New** → **Empty Service**
2. **Name**: `crowdvote-weekly-reset`
3. **Settings** → Connect to GitHub repo (same as main service)
4. **Settings** → Root Directory: `/` (same as main)

### 2. Configure Cron Schedule

**Settings** → **Cron Schedule**: `0 0 * * 0`

This runs every Sunday at midnight UTC (Saturday 7pm Eastern, 4pm Pacific).

### 3. Set Start Command

**Settings** → **Start Command**:
```bash
python manage.py generate_demo_communities --reset-database --create-admin
```

### 4. Configure Variables

**Variables** → **Add Reference Variables**:

Select your main web service and reference:
- `DATABASE_URL`
- `SECRET_KEY`
- `DEBUG` (set to `False`)

Or manually set:
```bash
DEBUG=False
```

And reference `DATABASE_URL` and `SECRET_KEY` from main service.

### 5. Deploy

Click **Deploy** and the cron will:
- Run every Sunday at midnight
- Wipe database completely
- Create fresh demo communities (Minions, Springfield, Test)
- Create 60+ users with delegation chains
- Create decisions with realistic timing
- Generate snapshots for open decisions
- Create demo admin user (`admin` / `admin`)
- Exit cleanly

Your main web service keeps running during the reset.

### 6. Monitor

**Deployments** → Click latest run → **View Logs**

Look for:
```
✅ Database wiped clean!
🔐 Demo admin created: admin/admin
✅ All snapshots created!
```

### 7. Test Before Waiting for Sunday

**Option A - Railway CLI:**
```bash
railway login
railway link  # Select crowdvote-weekly-reset service
railway run python manage.py generate_demo_communities --reset-database --create-admin
```

**Option B - Railway Dashboard:**
Service → Deployments → "Run Command" → Enter command above

---

## Summary Checklist

**Main Web Service:**
- [x] `DATABASE_URL` (from Railway PostgreSQL)
- [x] `SECRET_KEY` (generated)
- [x] `DEBUG=False`
- [x] `ALLOWED_HOSTS` (or use defaults)
- [x] Email settings (optional but recommended)

**Cron Service:**
- [x] Reference `DATABASE_URL` from main service
- [x] Reference `SECRET_KEY` from main service
- [x] `DEBUG=False`
- [x] Cron schedule: `0 0 * * 0`
- [x] Start command with `--reset-database --create-admin`

**Both services deployed?** ✅ Demo resets every Sunday automatically!
