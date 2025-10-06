# Plan #25: CAPTCHA Protection for Magic Link Requests

## Context

CrowdVote is receiving excessive bot signups (2135 emails sent in one week, 0% opens, 13% bounces) that are consuming our SendGrid free tier allocation (12,000 emails/month). The signup pattern shows clear bot behavior with sequential/random email addresses. We need to implement CAPTCHA protection on the magic link request form to block automated signups while preserving the user experience for legitimate users.

## CAPTCHA Solution: Cloudflare Turnstile

**Selected Solution**: Cloudflare Turnstile
- **Cost**: Free (no usage limits)
- **User Experience**: Invisible for 95% of users, simple checkbox for others
- **Implementation**: JavaScript library + server-side verification
- **Setup**: Requires free Cloudflare account
- **Privacy**: No personal data collection or tracking
- **Global Availability**: Works worldwide, including regions where Google services are blocked
- **Managed Mode**: Available for even more permissive human detection
- **Fallback Support**: Users who fail verification can contact support@crowdvote.com

## Technical Implementation Plan

### Phase 1: Service Setup and Configuration

#### 1.1 Cloudflare Turnstile Setup (User Action Required)

**Step-by-step setup for user:**

1. **Create Cloudflare Account** (5 minutes):
   - Go to https://dash.cloudflare.com/sign-up
   - Create free account with your email
   - Verify email if prompted

2. **Create Turnstile Site**:
   - Go to https://dash.cloudflare.com/?to=/:account/turnstile
   - Click "Add Site" button
   - **Domain**: Enter both `crowdvote.com` AND `localhost` for development
   - **Widget Mode**: Select "Managed" (most permissive for legitimate users)
   - **IMPORTANT**: Check the boxes next to each hostname to enable them
   - Click "Create"

3. **Copy Your Keys**:
   - **Site Key**: Starts with `0x4AAA...` (public, safe to expose)
   - **Secret Key**: Long random string (private, keep secure)

4. **Add to Railway Environment**:
   - Railway Dashboard → Your CrowdVote Project → "Variables" tab
   - Add these two variables:
     ```
     TURNSTILE_SITE_KEY=0x4AAA... (paste your site key)
     TURNSTILE_SECRET_KEY=0x4AAA... (paste your secret key)
     ```

**Important**: Use `crowdvote.com` as your domain in Turnstile setup since that's where users access your app. The Railway domain is just for deployment.

#### 1.2 Django Settings Configuration
**File**: `crowdvote/settings.py`
- Add Turnstile configuration variables
- Ensure keys are loaded from environment
- **CRITICAL**: Add `.env.local` file reading code:
  ```python
  # Read environment variables from .env.local file
  env_file = BASE_DIR / '.env.local'
  if env_file.exists():
      environ.Env.read_env(env_file)
  ```
  Without this, Docker Compose loads variables but Django can't access them.

### Phase 2: Frontend Integration

#### 2.1 Template Updates
**File**: `accounts/templates/accounts/request_magic_link.html`
- Add Turnstile JavaScript library
- Insert CAPTCHA widget div in form
- Add client-side validation

#### 2.2 Base Template Updates  
**File**: `crowdvote/templates/base.html`
- Add Turnstile script tag (if needed globally)
- Ensure CSP headers allow Turnstile domains

### Phase 3: Backend Verification

#### 3.1 Form Validation
**File**: `accounts/forms.py`
- Create new `CaptchaProtectedMagicLinkForm`
- Add `captcha_token` field
- Implement `clean_captcha_token()` method
- Make HTTP request to Turnstile verification API
- Validate response and handle errors

#### 3.2 View Updates
**File**: `accounts/views.py`
- Update `request_magic_link` view to use new form
- Handle CAPTCHA validation errors
- Add appropriate error messages
- Log failed CAPTCHA attempts for monitoring

#### 3.3 Utility Functions
**File**: `accounts/utils.py` (new functions)
- `verify_turnstile_token(token, user_ip)`: Server-side verification
- `get_client_ip(request)`: Extract real client IP
- Handle rate limiting integration

### Phase 4: Error Handling and UX

#### 4.1 Error Messages and Support Fallback
- User-friendly CAPTCHA failure messages
- Support contact for users who can't complete verification: "Having trouble? Email support@crowdvote.com"
- Clear instructions for users with JavaScript disabled
- Fallback behavior for accessibility

#### 4.2 Rate Limiting Integration
- Combine CAPTCHA with existing email rate limiting
- Stricter limits for failed CAPTCHA attempts
- IP-based tracking for repeat offenders

### Phase 5: Testing and Monitoring

#### 5.1 Test Coverage
**File**: `tests/test_forms/test_captcha_forms.py` (new)
- Mock Turnstile API responses
- Test successful verification
- Test failed verification scenarios
- Test network error handling

#### 5.2 Integration Tests
**File**: `tests/test_views/test_captcha_views.py` (new)
- End-to-end form submission tests
- CAPTCHA bypass attempt tests
- Rate limiting interaction tests

#### 5.3 Monitoring
- Log CAPTCHA success/failure rates
- Monitor bot signup reduction
- Track legitimate user impact

## Implementation Details

### Turnstile Integration Flow

1. **Frontend**: User submits magic link form
2. **JavaScript**: Turnstile generates token automatically
3. **Form**: Token included in form submission
4. **Django**: Server verifies token with Turnstile API
5. **Validation**: Proceed with magic link or show error

### API Verification Process

```python
def verify_turnstile_token(token, user_ip):
    """Verify Turnstile token with Cloudflare API."""
    response = requests.post(
        'https://challenges.cloudflare.com/turnstile/v0/siteverify',
        data={
            'secret': settings.TURNSTILE_SECRET_KEY,
            'response': token,
            'remoteip': user_ip,
        }
    )
    return response.json().get('success', False)
```

### Form Integration

```python
class CaptchaProtectedMagicLinkForm(forms.Form):
    email = forms.EmailField()
    captcha_token = forms.CharField(widget=forms.HiddenInput())
    
    def clean_captcha_token(self):
        token = self.cleaned_data.get('captcha_token')
        if not verify_turnstile_token(token, self.user_ip):
            raise forms.ValidationError("CAPTCHA verification failed.")
        return token
```

## Files to Create/Modify

### New Files
- `tests/test_forms/test_captcha_forms.py`
- `tests/test_views/test_captcha_views.py`

### Modified Files
- `crowdvote/settings.py` - Add Turnstile configuration
- `accounts/forms.py` - Add CAPTCHA-protected form
- `accounts/views.py` - Update magic link view
- `accounts/utils.py` - Add verification utilities
- `accounts/templates/accounts/request_magic_link.html` - Add CAPTCHA widget
- `requirements.txt` - Add requests library (if not present)
- `README.md` - Add bot protection documentation

## Environment Variables

Add to `.env.local` and production:
```
TURNSTILE_SITE_KEY=your_site_key_here
TURNSTILE_SECRET_KEY=your_secret_key_here
```

## Expected Outcomes

### Immediate Benefits
- 90%+ reduction in bot signups
- Preserved UX for legitimate users (invisible CAPTCHA)
- Reduced email service costs
- Better signup quality metrics

### Monitoring Metrics
- CAPTCHA success/failure rates
- Bot signup reduction percentage
- Legitimate user conversion impact
- Email bounce rate improvement

## Rollback Plan

If CAPTCHA causes issues:
1. Feature flag to disable CAPTCHA validation
2. Revert to original form without CAPTCHA
3. Monitor signup patterns for 24 hours
4. Re-enable with adjustments if needed

## Security Considerations

- Store secret keys securely in environment variables
- Validate all user inputs server-side
- Rate limit CAPTCHA verification requests
- Log suspicious activity patterns
- Consider IP allowlisting for known good sources

### Phase 6: Documentation Updates

#### 6.1 README.md Updates
**File**: `README.md`
- Add section under "Key Features" → "Technical Features":
  ```markdown
  - **Bot Protection**: Cloudflare Turnstile CAPTCHA prevents automated signups while remaining invisible to legitimate users
  ```
- Update installation section to mention CAPTCHA environment variables are optional for development

This plan prioritizes immediate bot protection while maintaining excellent user experience through invisible CAPTCHA technology.
