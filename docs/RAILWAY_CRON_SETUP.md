# Railway Cron Job Setup for CrowdVote Demo Reset

## Overview
To keep the demo fresh, we run a daily database reset that wipes all data and regenerates the demo communities with new users, decisions, and delegation chains. This allows visitors to join the Minions and Springfield communities at any time during the day and experience a realistic voting scenario.

## Configuration

### 1. Create Cron Service in Railway

1. In your Railway project dashboard, click **"New Service"**
2. Connect it to the same GitHub repository as your main web service
3. Set service name: **`crowdvote-demo-reset`**

### 2. Configure Cron Schedule

In the service settings, add the cron schedule:

**For daily reset at 12:01 PM** (adjust for your timezone):

- **PST (UTC-8)**: `1 20 * * *` (12:01 PM PST = 8:01 PM UTC)
- **EST (UTC-5)**: `1 17 * * *` (12:01 PM EST = 5:01 PM UTC)
- **CST (UTC-6)**: `1 18 * * *` (12:01 PM CST = 6:01 PM UTC)
- **UTC**: `1 12 * * *` (12:01 PM UTC)

**For weekly reset every Monday at 12:01 PM UTC**:
```
1 12 * * 1
```

Note: Railway cron jobs use UTC time. The cron expression format is:
```
* * * * *
│ │ │ │ │
│ │ │ │ └─────────── Day of the week (0-6, 0=Sunday)
│ │ │ └───────────── Month (1-12)
│ │ └─────────────── Day of the month (1-31)
│ └───────────────── Hour (0-23, UTC)
└─────────────────── Minute (0-59)
```

### 3. Set Start Command

Set the service start command to:
```bash
python manage.py generate_demo_communities --reset-database
```

**Important**: The command must complete and exit cleanly. Railway will run it on the scheduled time. The command:
- Wipes the entire database
- Creates 5 communities (2 auto-join, 3 application-required)
- Generates 60 users with realistic delegation chains
- Creates 8 themed decisions with varied close times
- Exits after completion

### 4. Environment Variables

The cron service needs the same environment variables as your main web service:

**Required Variables**:
- `DATABASE_URL`: Use Railway's service reference: `${{Postgres.DATABASE_URL}}`
- `SECRET_KEY`: Same value as your web service
- `DEBUG`: Set to **`False`** (prevents creating admin/admin superuser in production)
- `ALLOWED_HOSTS`: `.railway.app` or your custom domain
- `DJANGO_SETTINGS_MODULE`: `crowdvote.settings`

**Copy all other Django settings** from your main web service.

### 5. Railway Cron Job Requirements

From [Railway's cron job documentation](https://docs.railway.com/reference/cron-jobs):

✅ **Best Practices**:
- Service must exit when task completes (don't leave processes running)
- Minimum frequency: 5 minutes
- Use UTC timezone for scheduling
- Close all database connections before exiting
- Test the command locally first with `--reset-database` flag

❌ **Avoid**:
- Long-running processes that don't exit
- Sub-5-minute frequencies
- Relying on precise execution times (can vary by a few minutes)
- Using cron jobs for web servers or always-on services

### 6. What the Daily Reset Creates

When the cron job runs at 12:01 PM:

**Communities (5 total)**:
- 🍌 **Minion Collective** - Auto-join, 30 users, 4 decisions
- 🏭 **Springfield Town Council** - Auto-join, 30 users, 4 decisions
- 🏖️ **Ocean View Condo Association** - Application-required, 0 users
- 💻 **Tech Workers Cooperative** - Application-required, 0 users
- 🌱 **Riverside Community Garden** - Application-required, 0 users

**Decisions (8 total - 4 per community)**:
- 2 decisions already closed (1 hour ago)
- 2 decisions closing tomorrow (~23 hours)
- 2 decisions closing in 1 week
- 2 decisions closing in 2 weeks

**Members (60 total in Minions + Springfield)**:
- ~70% anonymous voting members
- ~30% public voting members
- All lobbyists are public (cannot be anonymous)
- Realistic delegation chains up to 4+ levels deep
- Some members not following anyone (disengaged)
- Some members not followed by anyone
- Circular delegation relationships for testing
- Mix of engaged and disengaged members

**Timing**: All close times are relative to reset time, so decisions always have fresh deadlines.

### 7. Monitoring

After setup, monitor your cron job:

1. **Check Railway Logs**: 
   - Open the cron service in Railway
   - View logs to see execution results
   - Look for success message: "Successfully generated realistic demo data!"

2. **Verify Data Resets**:
   - Visit your CrowdVote site after the scheduled time
   - Join Minions or Springfield community
   - Verify you see fresh decisions with varied close times

3. **Confirm Security**:
   - Ensure superuser is NOT created (DEBUG=False in production)
   - Only created locally when DEBUG=True

4. **Test Database State**:
   - 5 communities should exist
   - Minions and Springfield should have 30 members each
   - 3 application-required communities should be empty
   - 8 decisions with varied timing

### 8. Troubleshooting

**Cron job not running?**
- Verify cron expression syntax in service settings
- Check if previous execution is still running (Railway skips overlapping jobs)
- Review Railway logs for error messages
- Ensure minimum 5-minute interval between executions

**Database not resetting?**
- Verify `DATABASE_URL` environment variable is correct
- Check database connection permissions in Railway
- Test command locally: `docker-compose exec web python manage.py generate_demo_communities --reset-database`
- Review logs for Django database errors

**Superuser created in production?**
- Check `DEBUG` environment variable is set to `False`
- The command only creates admin/admin when DEBUG=True
- This is intentional - superuser should only exist in local development

**Execution time inconsistent?**
- Railway doesn't guarantee execution to the minute
- Jobs can vary by a few minutes
- This is normal behavior - adjust expectations accordingly

**Service won't exit?**
- Ensure no long-running processes in management command
- Check that all database connections are closed
- The `generate_demo_communities` command is designed to exit cleanly

### 9. Testing Locally

Before deploying to Railway, test the command locally:

```bash
# In local development (creates admin/admin superuser)
docker-compose exec web python manage.py generate_demo_communities --reset-database

# Verify output shows:
# - 5 communities created
# - 60 users generated
# - 8 decisions with varied timing
# - 🔐 Superuser: admin/admin (DEBUG mode)

# Test the data:
# - Visit http://localhost:8000
# - Join Minions or Springfield
# - Vote on active decisions
# - View delegation network
# - Verify anonymity features work
```

### 10. Production Deployment Checklist

Before enabling the cron job in production:

- [ ] Command tested locally with `--reset-database` flag
- [ ] Railway cron service created and connected to GitHub
- [ ] Cron schedule configured (daily at 12:01 PM in your timezone)
- [ ] Start command set: `python manage.py generate_demo_communities --reset-database`
- [ ] All environment variables copied from web service
- [ ] `DEBUG` set to `False` in cron service
- [ ] `DATABASE_URL` points to production database
- [ ] Logs monitored for first execution
- [ ] Data reset verified on website
- [ ] No superuser created in production (verified in logs)

## Support

For Railway-specific issues, consult:
- [Railway Cron Jobs Documentation](https://docs.railway.com/reference/cron-jobs)
- [Railway Discord Community](https://discord.gg/railway)

For CrowdVote command issues:
- Review `democracy/management/commands/generate_demo_communities.py`
- Check `docs/CHANGELOG.md` for recent changes
- Test locally with Docker Compose

---

**Last Updated**: Plan 0006 - Membership-Level Anonymity System

