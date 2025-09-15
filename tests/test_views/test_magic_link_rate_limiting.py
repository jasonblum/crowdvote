"""
Tests for magic link rate limiting functionality.

This module tests the rate limiting implementation for magic link requests,
ensuring that abuse protection works correctly while allowing legitimate users
to access the system.
"""
import time
from unittest.mock import patch, Mock
from django.test import TestCase, Client
from django.urls import reverse
from django.core.cache import cache
from django.contrib.messages import get_messages
from django.conf import settings


class MagicLinkRateLimitingTest(TestCase):
    """Test rate limiting for magic link requests."""
    
    def setUp(self):
        """Set up test client and clear cache."""
        self.client = Client()
        self.magic_link_url = reverse('accounts:request_magic_link')
        cache.clear()
    
    def tearDown(self):
        """Clean up cache after each test."""
        cache.clear()
    
    def test_first_request_allowed(self):
        """Test that first magic link request is allowed."""
        with patch('accounts.views.send_mail') as mock_send_mail:
            response = self.client.post(self.magic_link_url, {
                'email': 'test@example.com'
            })
            
            self.assertEqual(response.status_code, 302)
            mock_send_mail.assert_called_once()
            
            messages = list(get_messages(response.wsgi_request))
            self.assertEqual(len(messages), 1)
            self.assertIn('Magic link sent', str(messages[0]))
            self.assertIn('(Limit: 3 requests per hour)', str(messages[0]))
    
    def test_ip_rate_limit_enforcement(self):
        """Test that IP-based rate limiting works correctly."""
        email = 'test@example.com'
        
        with patch('accounts.views.send_mail') as mock_send_mail:
            # Make 3 successful requests (should all work)
            for i in range(3):
                response = self.client.post(self.magic_link_url, {
                    'email': f'test{i}@example.com'  # Different emails, same IP
                })
                self.assertEqual(response.status_code, 302)
                mock_send_mail.assert_called()
                
                # Wait a bit to avoid minimum interval limit
                time.sleep(0.1)
            
            # 4th request should be blocked
            response = self.client.post(self.magic_link_url, {
                'email': 'test4@example.com'
            })
            
            self.assertEqual(response.status_code, 302)
            messages = list(get_messages(response.wsgi_request))
            # Should have 4 messages total: 3 success + 1 error
            self.assertEqual(len(messages), 4)
            # Last message should be the rate limit error
            last_message = str(messages[-1])
            self.assertIn('Too many requests from your location', last_message)
            self.assertIn('(Limit: 3 per hour)', last_message)
    
    def test_email_rate_limit_enforcement(self):
        """Test that email-based rate limiting works correctly."""
        email = 'test@example.com'
        
        with patch('accounts.views.send_mail') as mock_send_mail:
            # Make 3 requests to same email from different IPs
            for i in range(3):
                # Simulate different IP addresses
                with patch.object(self.client, 'post') as mock_post:
                    mock_request = Mock()
                    mock_request.POST = {'email': email}
                    mock_request.META = {
                        'REMOTE_ADDR': f'192.168.1.{i+1}',
                        'HTTP_X_FORWARDED_FOR': None
                    }
                    
                    response = self.client.post(self.magic_link_url, {
                        'email': email
                    }, REMOTE_ADDR=f'192.168.1.{i+1}')
                    
                    self.assertEqual(response.status_code, 302)
                    time.sleep(0.1)  # Avoid minimum interval
            
            # 4th request to same email should be blocked
            response = self.client.post(self.magic_link_url, {
                'email': email
            }, REMOTE_ADDR='192.168.1.4')
            
            messages = list(get_messages(response.wsgi_request))
            # Find the rate limit error message
            rate_limit_messages = [msg for msg in messages if 'Too many magic links requested' in str(msg)]
            self.assertEqual(len(rate_limit_messages), 1)
            self.assertIn(f'Too many magic links requested for {email}', str(rate_limit_messages[0]))
    
    def test_minimum_interval_enforcement(self):
        """Test that 15-minute minimum interval is enforced."""
        email = 'test@example.com'
        
        with patch('accounts.views.send_mail') as mock_send_mail:
            # First request should work
            response = self.client.post(self.magic_link_url, {
                'email': email
            })
            self.assertEqual(response.status_code, 302)
            mock_send_mail.assert_called()
            
            # Immediate second request should be blocked
            response = self.client.post(self.magic_link_url, {
                'email': email
            })
            
            messages = list(get_messages(response.wsgi_request))
            # Should have 2 messages: 1 success + 1 error
            self.assertEqual(len(messages), 2)
            # Last message should be the rate limit error
            message_text = str(messages[-1])
            self.assertIn('Please wait', message_text)
            self.assertIn('minutes before requesting another', message_text)
    
    def test_rate_limit_reset_after_hour(self):
        """Test that rate limits reset after 1 hour."""
        email = 'test@example.com'
        
        with patch('accounts.views.send_mail') as mock_send_mail:
            # Fill up the rate limit
            for i in range(3):
                response = self.client.post(self.magic_link_url, {
                    'email': f'test{i}@example.com'
                })
                self.assertEqual(response.status_code, 302)
                time.sleep(0.1)
            
            # Should be blocked now
            response = self.client.post(self.magic_link_url, {
                'email': 'blocked@example.com'
            })
            messages = list(get_messages(response.wsgi_request))
            self.assertIn('Too many requests', str(messages[0]))
            
            # Simulate cache expiry (1 hour later)
            cache.clear()
            
            # Should work again
            response = self.client.post(self.magic_link_url, {
                'email': 'allowed@example.com'
            })
            self.assertEqual(response.status_code, 302)
            mock_send_mail.assert_called()
    
    def test_different_ips_independent_limits(self):
        """Test that different IP addresses have independent rate limits."""
        with patch('accounts.views.send_mail') as mock_send_mail:
            # Fill up limit for first IP
            for i in range(3):
                response = self.client.post(self.magic_link_url, {
                    'email': f'test{i}@example.com'
                }, REMOTE_ADDR='192.168.1.1')
                self.assertEqual(response.status_code, 302)
                time.sleep(0.1)
            
            # First IP should be blocked
            response = self.client.post(self.magic_link_url, {
                'email': 'blocked@example.com'
            }, REMOTE_ADDR='192.168.1.1')
            messages = list(get_messages(response.wsgi_request))
            self.assertIn('Too many requests', str(messages[0]))
            
            # Different IP should still work
            response = self.client.post(self.magic_link_url, {
                'email': 'allowed@example.com'
            }, REMOTE_ADDR='192.168.1.2')
            self.assertEqual(response.status_code, 302)
            mock_send_mail.assert_called()
    
    def test_email_includes_support_footer(self):
        """Test that magic link emails include support contact information."""
        with patch('accounts.views.send_mail') as mock_send_mail:
            response = self.client.post(self.magic_link_url, {
                'email': 'test@example.com'
            })
            
            self.assertEqual(response.status_code, 302)
            mock_send_mail.assert_called_once()
            
            # Check email content includes support footer
            call_args = mock_send_mail.call_args
            email_message = call_args[1]['message']  # message is a keyword argument
            self.assertIn('Questions? Contact support@crowdvote.com', email_message)
    
    def test_success_message_includes_rate_limit_info(self):
        """Test that success message mentions rate limiting."""
        with patch('accounts.views.send_mail') as mock_send_mail:
            response = self.client.post(self.magic_link_url, {
                'email': 'test@example.com'
            })
            
            messages = list(get_messages(response.wsgi_request))
            self.assertEqual(len(messages), 1)
            message_text = str(messages[0])
            self.assertIn('Magic link sent', message_text)
            self.assertIn('(Limit: 3 requests per hour)', message_text)
    
    def test_x_forwarded_for_header_handling(self):
        """Test that X-Forwarded-For header is properly handled for IP detection."""
        with patch('accounts.views.send_mail') as mock_send_mail:
            # Test with X-Forwarded-For header (common in production behind proxies)
            response = self.client.post(self.magic_link_url, {
                'email': 'test@example.com'
            }, HTTP_X_FORWARDED_FOR='203.0.113.1, 192.168.1.1')
            
            self.assertEqual(response.status_code, 302)
            mock_send_mail.assert_called_once()
            
            # The rate limiting should use the first IP from X-Forwarded-For
            # Make 2 more requests to fill the limit
            for i in range(2):
                response = self.client.post(self.magic_link_url, {
                    'email': f'test{i}@example.com'
                }, HTTP_X_FORWARDED_FOR='203.0.113.1, 192.168.1.1')
                time.sleep(0.1)
            
            # 4th request should be blocked
            response = self.client.post(self.magic_link_url, {
                'email': 'blocked@example.com'
            }, HTTP_X_FORWARDED_FOR='203.0.113.1, 192.168.1.1')
            
            messages = list(get_messages(response.wsgi_request))
            self.assertIn('Too many requests from your location', str(messages[0]))
    
    def test_invalid_email_not_rate_limited(self):
        """Test that invalid email requests don't count against rate limits."""
        with patch('accounts.views.send_mail') as mock_send_mail:
            # Make request with empty email
            response = self.client.post(self.magic_link_url, {
                'email': ''
            })
            
            messages = list(get_messages(response.wsgi_request))
            self.assertIn('Please enter a valid email address', str(messages[0]))
            mock_send_mail.assert_not_called()
            
            # Should still be able to make valid requests
            response = self.client.post(self.magic_link_url, {
                'email': 'valid@example.com'
            })
            self.assertEqual(response.status_code, 302)
            mock_send_mail.assert_called_once()
    
    def test_email_send_failure_doesnt_update_limits(self):
        """Test that failed email sends don't update rate limit counters."""
        with patch('accounts.views.send_mail', side_effect=Exception('Email failed')):
            response = self.client.post(self.magic_link_url, {
                'email': 'test@example.com'
            })
            
            # Should get error message
            messages = list(get_messages(response.wsgi_request))
            self.assertEqual(len(messages), 1)
            self.assertIn("couldn't send your magic link", str(messages[0]))
            
            # Rate limit counter should not be updated, so next request should work
            with patch('accounts.views.send_mail') as mock_send_mail:
                response = self.client.post(self.magic_link_url, {
                    'email': 'test@example.com'
                })
                self.assertEqual(response.status_code, 302)
                mock_send_mail.assert_called_once()
    
    @patch('accounts.views.settings.MAGIC_LINK_RATE_LIMIT_PER_HOUR', 1)
    @patch('accounts.views.settings.MAGIC_LINK_MIN_INTERVAL_MINUTES', 1)
    def test_custom_rate_limit_settings(self):
        """Test that custom rate limit settings are respected."""
        with patch('accounts.views.send_mail') as mock_send_mail:
            # First request should work
            response = self.client.post(self.magic_link_url, {
                'email': 'test@example.com'
            })
            self.assertEqual(response.status_code, 302)
            
            # Second request should be blocked (limit is 1)
            response = self.client.post(self.magic_link_url, {
                'email': 'test2@example.com'
            })
            
            messages = list(get_messages(response.wsgi_request))
            self.assertIn('Too many requests', str(messages[0]))
            self.assertIn('(Limit: 1 per hour)', str(messages[0]))
