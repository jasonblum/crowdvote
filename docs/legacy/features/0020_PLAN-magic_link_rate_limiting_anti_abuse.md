# Plan #20: Magic Link Rate Limiting & Anti-Abuse Protection

## Context

CrowdVote's magic link authentication system is experiencing high volume (841 requests in one week) from potentially automated sources. While users can only vote on existing decisions and cannot create communities or decisions without admin privileges, the email volume threatens to exceed SendPulse's 12,000/month free tier limit. This plan implements rate limiting and user communication improvements to prevent abuse while maintaining a smooth experience for legitimate users.

## Technical Requirements

### Rate Limiting Implementation

**File: `accounts/views.py`**
- Modify `request_magic_link()` function to implement dual rate limiting:
  - **Per IP Address**: Maximum 3 requests per hour, minimum 15 minutes between requests
  - **Per Email Address**: Maximum 3 requests per hour, minimum 15 minutes between requests
- Use Django's default cache framework for rate limit storage (no Redis required)
- Return appropriate error messages when limits are exceeded
- Log rate limit violations for monitoring

**Rate Limiting Logic:**
1. Check IP address rate limit first (3/hour, 15min minimum)
2. If IP passes, check email address rate limit (3/hour, 15min minimum)  
3. If both pass, create magic link and increment both counters
4. If either fails, return user-friendly error message with time remaining
5. Use cache keys: `magic_link_ip:{ip}` and `magic_link_email:{email}`

### User Communication Updates

**File: `accounts/views.py`**
- Update success message in `request_magic_link()` to include rate limiting information
- Current message: "✨ Magic link sent to {email}! Check your email and click the link to sign in."
- New message: "✨ Magic link sent to {email}! Check your email and click the link to sign in. (Limit: 3 requests per hour)"

**File: `accounts/views.py`**  
- Update magic link email template to include support footer
- Add footer text: "Questions? Contact support@crowdvote.com"
- Maintain existing 15-minute expiration messaging

### Error Handling & User Feedback

**Rate Limit Error Messages:**
- IP rate limit exceeded: "Too many requests from your location. Please wait {minutes} minutes before requesting another magic link. (Limit: 3 per hour)"
- Email rate limit exceeded: "Too many magic links requested for {email}. Please wait {minutes} minutes before requesting another. (Limit: 3 per hour)"
- Both limits exceeded: Show the longer wait time

### Settings Configuration

**File: `crowdvote/settings.py`**
- Add rate limiting configuration constants:
  - `MAGIC_LINK_RATE_LIMIT_PER_HOUR = 3`
  - `MAGIC_LINK_MIN_INTERVAL_MINUTES = 15`
- Django's default cache backend will be used (no additional configuration needed)

### Testing Requirements

**File: `tests/test_views/test_magic_link_rate_limiting.py`** (new)
- Test IP-based rate limiting (3 requests, then blocked)
- Test email-based rate limiting (3 requests, then blocked)
- Test minimum 15-minute interval enforcement
- Test rate limit reset after 1 hour
- Test appropriate error messages for each limit type
- Test that legitimate requests still work within limits
- Test concurrent requests from different IPs/emails

**Update existing tests:**
- `tests/test_views/test_accounts_views.py` - Update magic link tests to account for rate limiting
- Ensure existing magic link functionality tests still pass

## Implementation Notes

- Use Django's default cache framework with timeout-based keys for automatic cleanup
- Rate limits are per IP and per email independently (both must pass)
- 15-minute minimum interval prevents rapid-fire requests even within hourly limit
- Cache keys expire automatically after 1 hour, resetting limits
- Preserve all existing magic link functionality and security features
- Maintain backward compatibility with existing magic link URLs and tokens

## Files to Modify

1. `accounts/views.py` - Add rate limiting logic to `request_magic_link()`
2. `crowdvote/settings.py` - Add rate limiting configuration constants  
3. `tests/test_views/test_magic_link_rate_limiting.py` - New comprehensive test file
4. `tests/test_views/test_accounts_views.py` - Update existing tests for rate limiting

## Success Criteria

- Magic link requests are limited to 3 per hour per IP and per email
- Minimum 15-minute interval enforced between requests
- Clear, helpful error messages when limits exceeded
- Email includes support contact information
- Success message mentions rate limiting
- All existing functionality preserved
- Comprehensive test coverage for all rate limiting scenarios
