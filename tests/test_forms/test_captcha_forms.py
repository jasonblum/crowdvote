"""
Tests for CAPTCHA-protected forms.

This module tests the Turnstile CAPTCHA integration in CrowdVote forms,
including form validation, token verification, and error handling.
"""

import pytest
from unittest.mock import patch, Mock
from django.test import RequestFactory
from accounts.forms import CaptchaProtectedMagicLinkForm
from accounts.utils import verify_turnstile_token, get_client_ip


class TestCaptchaProtectedMagicLinkForm:
    """Test the CAPTCHA-protected magic link form."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        
    def test_form_valid_with_captcha_token(self):
        """Test form validation with valid CAPTCHA token."""
        request = self.factory.post('/', {'email': 'test@example.com', 'captcha_token': 'valid_token'})
        
        with patch('accounts.forms.verify_turnstile_token', return_value=True):
            form = CaptchaProtectedMagicLinkForm(
                data={'email': 'test@example.com', 'captcha_token': 'valid_token'},
                request=request
            )
            assert form.is_valid()
            
    def test_form_invalid_with_bad_captcha_token(self):
        """Test form validation with invalid CAPTCHA token."""
        request = self.factory.post('/', {'email': 'test@example.com', 'captcha_token': 'invalid_token'})
        
        with patch('accounts.forms.verify_turnstile_token', return_value=False):
            form = CaptchaProtectedMagicLinkForm(
                data={'email': 'test@example.com', 'captcha_token': 'invalid_token'},
                request=request
            )
            assert not form.is_valid()
            assert 'CAPTCHA verification failed' in str(form.errors['captcha_token'])
            
    def test_form_invalid_without_request_context(self):
        """Test form validation fails without request context."""
        form = CaptchaProtectedMagicLinkForm(
            data={'email': 'test@example.com', 'captcha_token': 'token'}
        )
        assert not form.is_valid()
        assert 'Request context required' in str(form.errors['captcha_token'])
        
    def test_form_valid_email_validation(self):
        """Test email field validation."""
        request = self.factory.post('/', {})
        
        # Invalid email
        form = CaptchaProtectedMagicLinkForm(
            data={'email': 'invalid-email', 'captcha_token': 'token'},
            request=request
        )
        assert not form.is_valid()
        assert 'email' in form.errors
        
        # Valid email
        with patch('accounts.forms.verify_turnstile_token', return_value=True):
            form = CaptchaProtectedMagicLinkForm(
                data={'email': 'valid@example.com', 'captcha_token': 'token'},
                request=request
            )
            assert form.is_valid()


class TestTurnstileUtilities:
    """Test Turnstile utility functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        
    def test_get_client_ip_with_forwarded_header(self):
        """Test IP extraction with X-Forwarded-For header."""
        request = self.factory.get('/', HTTP_X_FORWARDED_FOR='192.168.1.1, 10.0.0.1')
        ip = get_client_ip(request)
        assert ip == '192.168.1.1'
        
    def test_get_client_ip_without_forwarded_header(self):
        """Test IP extraction without X-Forwarded-For header."""
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
        ip = get_client_ip(request)
        assert ip == '192.168.1.100'
        
    @patch('accounts.utils.requests.post')
    def test_verify_turnstile_token_success(self, mock_post):
        """Test successful Turnstile token verification."""
        mock_response = Mock()
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        result = verify_turnstile_token('valid_token', '192.168.1.1')
        assert result is True
        
        mock_post.assert_called_once_with(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': '',  # Will be empty in test settings
                'response': 'valid_token',
                'remoteip': '192.168.1.1',
            },
            timeout=10
        )
        
    @patch('accounts.utils.requests.post')
    def test_verify_turnstile_token_failure(self, mock_post):
        """Test failed Turnstile token verification."""
        mock_response = Mock()
        mock_response.json.return_value = {'success': False, 'error-codes': ['invalid-input-response']}
        mock_post.return_value = mock_response
        
        result = verify_turnstile_token('invalid_token', '192.168.1.1')
        assert result is False
        
    @patch('accounts.utils.requests.post')
    def test_verify_turnstile_token_network_error(self, mock_post):
        """Test Turnstile verification with network error."""
        mock_post.side_effect = Exception('Network error')
        
        result = verify_turnstile_token('token', '192.168.1.1')
        assert result is False
        
    def test_verify_turnstile_token_no_token(self):
        """Test Turnstile verification with no token."""
        result = verify_turnstile_token('', '192.168.1.1')
        assert result is False
        
        result = verify_turnstile_token(None, '192.168.1.1')
        assert result is False
        
    @patch('accounts.utils.settings.TURNSTILE_SECRET_KEY', '')
    def test_verify_turnstile_token_no_secret_key(self):
        """Test Turnstile verification with no secret key configured."""
        result = verify_turnstile_token('token', '192.168.1.1')
        assert result is True  # Should allow requests when CAPTCHA not configured
