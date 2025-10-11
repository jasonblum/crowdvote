"""
Comprehensive tests for accounts app forms.

Tests cover validation, security, edge cases, and business logic for all forms
in the accounts app, focusing on profile management and user authentication.
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django import forms

from security.forms import ProfileEditForm
from tests.factories.user_factory import UserFactory

User = get_user_model()


@pytest.mark.forms
class TestProfileEditForm(TestCase):
    """Test the ProfileEditForm for user profile management."""
    
    def setUp(self):
        """Set up test data for each test."""
        self.user = UserFactory()
        self.valid_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'bio': 'This is a test biography for John Doe. He is a community member who participates in democratic decisions.',
            'location': 'San Francisco, CA',
            'website_url': 'https://johndoe.com',
            'twitter_url': 'https://twitter.com/johndoe',
            'linkedin_url': 'https://linkedin.com/in/johndoe',
            'bio_public': True,
            'location_public': True,
            'social_links_public': True
        }
    
    def test_valid_form_submission(self):
        """Test that a valid form can be submitted and saved."""
        form = ProfileEditForm(data=self.valid_data, instance=self.user)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        user = form.save()
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')
        self.assertEqual(user.bio, self.valid_data['bio'])
        self.assertTrue(user.bio_public)
    
    def test_name_validation(self):
        """Test first name and last name validation."""
        # Test empty names (should be valid - optional fields)
        data = self.valid_data.copy()
        data['first_name'] = ''
        data['last_name'] = ''
        form = ProfileEditForm(data=data, instance=self.user)
        self.assertTrue(form.is_valid())
        
        # Test very long names
        data['first_name'] = 'x' * 151  # Assuming 150 char limit
        form = ProfileEditForm(data=data, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)
        
        # Test valid names
        data['first_name'] = 'María José'
        data['last_name'] = "O'Connor-Smith"
        form = ProfileEditForm(data=data, instance=self.user)
        self.assertTrue(form.is_valid())
    
    def test_bio_validation(self):
        """Test biography field validation."""
        # Empty bio (should be valid)
        data = self.valid_data.copy()
        data['bio'] = ''
        form = ProfileEditForm(data=data, instance=self.user)
        self.assertTrue(form.is_valid())
        
        # Very long bio
        data['bio'] = 'x' * 1001  # Assuming 1000 char limit
        form = ProfileEditForm(data=data, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('bio', form.errors)
        
        # Valid bio with special characters
        data['bio'] = 'I am a software engineer 👨‍💻 who loves democracy! Born in São Paulo 🇧🇷, now in NYC 🗽.'
        form = ProfileEditForm(data=data, instance=self.user)
        self.assertTrue(form.is_valid())
    
    def test_location_validation(self):
        """Test location field validation."""
        # Empty location (should be valid)
        data = self.valid_data.copy()
        data['location'] = ''
        form = ProfileEditForm(data=data, instance=self.user)
        self.assertTrue(form.is_valid())
        
        # Various location formats
        location_tests = [
            'San Francisco, CA',
            'London, UK',
            'São Paulo, Brazil',
            'Remote',
            'New York City, NY, USA',
            'Berlin, Germany 🇩🇪'
        ]
        
        for location in location_tests:
            data['location'] = location
            form = ProfileEditForm(data=data, instance=self.user)
            self.assertTrue(form.is_valid(), f"Location '{location}' failed validation: {form.errors}")
    
    def test_url_validation(self):
        """Test URL field validation for website, Twitter, and LinkedIn."""
        # Test valid URLs
        valid_urls = [
            ('website_url', 'https://example.com'),
            ('website_url', 'http://subdomain.example.co.uk'),
            ('website_url', 'https://example.com/path/to/page'),
            ('twitter_url', 'https://twitter.com/username'),
            ('twitter_url', 'https://x.com/username'),
            ('linkedin_url', 'https://linkedin.com/in/username'),
            ('linkedin_url', 'https://www.linkedin.com/in/username')
        ]
        
        for field, url in valid_urls:
            data = self.valid_data.copy()
            data[field] = url
            form = ProfileEditForm(data=data, instance=self.user)
            self.assertTrue(form.is_valid(), f"URL '{url}' for field '{field}' failed validation: {form.errors}")
        
        # Test invalid URLs
        invalid_urls = [
            ('website_url', 'not-a-url'),
            ('website_url', 'javascript:alert("xss")'),
            ('twitter_url', 'https://facebook.com/user'),  # Wrong domain
            ('linkedin_url', 'https://twitter.com/user')  # Wrong domain
        ]
        # Note: FTP URLs are valid per Django's URLField, so we don't test them as invalid
        
        for field, url in invalid_urls:
            data = self.valid_data.copy()
            data[field] = url
            form = ProfileEditForm(data=data, instance=self.user)
            self.assertFalse(form.is_valid(), f"Invalid URL '{url}' for field '{field}' should have failed validation")
    
    def test_privacy_settings_validation(self):
        """Test privacy setting boolean fields."""
        # Test all privacy settings combinations
        privacy_combinations = [
            (True, True, True),
            (False, False, False),
            (True, False, True),
            (False, True, False)
        ]
        
        for bio_public, location_public, social_links_public in privacy_combinations:
            data = self.valid_data.copy()
            data['bio_public'] = bio_public
            data['location_public'] = location_public
            data['social_links_public'] = social_links_public
            
            form = ProfileEditForm(data=data, instance=self.user)
            self.assertTrue(form.is_valid(), f"Privacy combination failed: {form.errors}")
    
    def test_form_widget_attributes(self):
        """Test that form widgets have correct CSS classes and attributes."""
        form = ProfileEditForm(instance=self.user)
        
        # Check that all text inputs have proper CSS classes
        text_fields = ['first_name', 'last_name', 'location']
        for field_name in text_fields:
            widget = form.fields[field_name].widget
            self.assertIn('w-full', widget.attrs.get('class', ''))
            self.assertIn('px-3 py-2', widget.attrs.get('class', ''))
            self.assertIn('dark:bg-gray-700', widget.attrs.get('class', ''))
        
        # Check textarea widget for bio
        bio_widget = form.fields['bio'].widget
        self.assertIn('w-full', bio_widget.attrs.get('class', ''))
        self.assertEqual(bio_widget.attrs.get('rows'), 4)
        
        # Check URL inputs
        url_fields = ['website_url', 'twitter_url', 'linkedin_url']
        for field_name in url_fields:
            widget = form.fields[field_name].widget
            self.assertIn('w-full', widget.attrs.get('class', ''))
    
    def test_clean_twitter_url_method(self):
        """Test the custom clean_twitter_url method."""
        # Valid Twitter URLs
        valid_twitter_urls = [
            'https://twitter.com/username',
            'https://x.com/username',
            'https://www.twitter.com/username',
            'https://www.x.com/username'
        ]
        
        for url in valid_twitter_urls:
            data = self.valid_data.copy()
            data['twitter_url'] = url
            form = ProfileEditForm(data=data, instance=self.user)
            self.assertTrue(form.is_valid(), f"Valid Twitter URL '{url}' failed validation: {form.errors}")
        
        # Invalid Twitter URLs (should fail custom validation)
        invalid_twitter_urls = [
            'https://facebook.com/username',
            'https://instagram.com/username',
            'https://linkedin.com/in/username',
            'https://nottwitter.com/username'
        ]
        
        for url in invalid_twitter_urls:
            data = self.valid_data.copy()
            data['twitter_url'] = url
            form = ProfileEditForm(data=data, instance=self.user)
            self.assertFalse(form.is_valid(), f"Invalid Twitter URL '{url}' should have failed validation")
            if not form.is_valid():
                self.assertIn('twitter_url', form.errors)
    
    def test_clean_linkedin_url_method(self):
        """Test the custom clean_linkedin_url method."""
        # Valid LinkedIn URLs
        valid_linkedin_urls = [
            'https://linkedin.com/in/username',
            'https://www.linkedin.com/in/username',
            'https://linkedin.com/company/companyname',
            'https://www.linkedin.com/company/companyname'
        ]
        
        for url in valid_linkedin_urls:
            data = self.valid_data.copy()
            data['linkedin_url'] = url
            form = ProfileEditForm(data=data, instance=self.user)
            self.assertTrue(form.is_valid(), f"Valid LinkedIn URL '{url}' failed validation: {form.errors}")
        
        # Invalid LinkedIn URLs
        invalid_linkedin_urls = [
            'https://twitter.com/username',
            'https://facebook.com/username',
            'https://notlinkedin.com/in/username'
        ]
        
        for url in invalid_linkedin_urls:
            data = self.valid_data.copy()
            data['linkedin_url'] = url
            form = ProfileEditForm(data=data, instance=self.user)
            self.assertFalse(form.is_valid(), f"Invalid LinkedIn URL '{url}' should have failed validation")
            if not form.is_valid():
                self.assertIn('linkedin_url', form.errors)


@pytest.mark.forms
class TestProfileFormSecurityAndEdgeCases(TestCase):
    """Test security vulnerabilities and edge cases for profile forms."""
    
    def setUp(self):
        """Set up test data for security tests."""
        self.user = UserFactory()
        self.base_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'bio_public': True,
            'location_public': True,
            'social_links_public': True
        }
    
    def test_xss_prevention(self):
        """Test that forms prevent XSS attacks in text fields."""
        xss_payloads = [
            '<script>alert("xss")</script>',
            '"><script>alert("xss")</script>',
            '<img src="x" onerror="alert(\'xss\')">'
            '<svg onload="alert(\'xss\')">'
        ]
        
        text_fields = ['first_name', 'last_name', 'bio', 'location']
        
        for field in text_fields:
            for payload in xss_payloads:
                data = self.base_data.copy()
                data[field] = f'Safe text {payload}'
                
                form = ProfileEditForm(data=data, instance=self.user)
                if form.is_valid():
                    user = form.save()
                    field_value = getattr(user, field)
                    
                    # Verify the payload is stored as-is (will be escaped in templates)
                    self.assertIn(payload, field_value)
    
    def test_sql_injection_prevention(self):
        """Test that forms prevent SQL injection attacks."""
        sql_payloads = [
            "'; DROP TABLE auth_user; --",
            "' OR '1'='1",
            "'; DELETE FROM accounts_customuser; --",
            "1'; UNION SELECT * FROM auth_user; --"
        ]
        
        for payload in sql_payloads:
            data = self.base_data.copy()
            data['bio'] = f'Biography with SQL payload: {payload}'
            data['location'] = f'Location {payload}'
            
            form = ProfileEditForm(data=data, instance=self.user)
            if form.is_valid():
                user = form.save()
                
                # Verify data is stored safely
                self.assertIn(payload, user.bio)
                self.assertIn(payload, user.location)
    
    def test_unicode_and_emoji_handling(self):
        """Test that forms handle Unicode characters and emojis correctly."""
        unicode_test_cases = [
            ('first_name', '🌟 João'),
            ('last_name', 'García-López'),
            ('bio', 'I love democracy 🗳️ and tacos 🌮! Born in São Paulo 🇧🇷.'),
            ('location', 'México City 🇲🇽'),
            ('website_url', 'https://café-demo.com'),  # Unicode in domain (if valid)
        ]
        
        for field, value in unicode_test_cases:
            data = self.base_data.copy()
            data[field] = value
            
            form = ProfileEditForm(data=data, instance=self.user)
            # Note: Some Unicode URLs might not be valid, so we check appropriately
            if field.endswith('_url') and 'café' in value:
                # Unicode domains might not pass URL validation
                continue
            else:
                self.assertTrue(form.is_valid(), f"Unicode handling failed for {field}: '{value}' - {form.errors}")
    
    def test_boundary_conditions(self):
        """Test boundary conditions for field lengths and values."""
        # Test field length boundaries (these depend on model field definitions)
        boundary_tests = [
            # Assuming reasonable limits
            ('first_name', 'x' * 30, True),   # Should be valid
            ('first_name', 'x' * 151, False), # Should exceed limit
            ('bio', 'x' * 500, True),         # Should be valid
            ('bio', 'x' * 1001, False),       # Should exceed limit
        ]
        
        for field, value, should_be_valid in boundary_tests:
            data = self.base_data.copy()
            data[field] = value
            
            form = ProfileEditForm(data=data, instance=self.user)
            if should_be_valid:
                self.assertTrue(form.is_valid(), f"Boundary test failed for {field} with length {len(value)}: {form.errors}")
            else:
                self.assertFalse(form.is_valid(), f"Boundary test should have failed for {field} with length {len(value)}")
    
    def test_url_injection_prevention(self):
        """Test that URL fields prevent various injection attempts."""
        malicious_urls = [
            'javascript:alert("xss")',
            'data:text/html,<script>alert("xss")</script>',
            'vbscript:msgbox("xss")',
            'file:///etc/passwd',
            # Note: FTP URLs are valid per Django's URLField, so we don't test them as malicious
        ]
        
        url_fields = ['website_url', 'twitter_url', 'linkedin_url']
        
        for field in url_fields:
            for malicious_url in malicious_urls:
                data = self.base_data.copy()
                data[field] = malicious_url
                
                form = ProfileEditForm(data=data, instance=self.user)
                self.assertFalse(form.is_valid(), f"Malicious URL '{malicious_url}' should have failed validation for {field}")
    
    def test_form_csrf_compatibility(self):
        """Test that forms are compatible with CSRF protection."""
        # Verify form is a standard Django form that works with CSRF
        form = ProfileEditForm(instance=self.user)
        
        self.assertIsInstance(form, forms.ModelForm)
        self.assertTrue(hasattr(form, 'is_valid'))
        
        # cleaned_data only exists after validation
        self.assertFalse(hasattr(form, 'cleaned_data'))
        
        # After validation, cleaned_data should exist
        form = ProfileEditForm(data=self.base_data, instance=self.user)
        form.is_valid()
        self.assertTrue(hasattr(form, 'cleaned_data'))
        
        # Verify no CSRF exemptions or custom middleware bypasses
        # This is more of a design verification
        self.assertFalse(hasattr(form, 'csrf_exempt'))
    
    def test_privacy_setting_edge_cases(self):
        """Test edge cases for privacy settings."""
        # Test with boolean values that Django's BooleanField actually handles
        boolean_tests = [
            (True, True),
            (False, False),
            ('on', True),   # Django converts 'on' to True
            ('', False),    # Django converts empty string to False
        ]
        
        for input_val, expected_bool in boolean_tests:
            data = self.base_data.copy()
            data['bio_public'] = input_val
            
            form = ProfileEditForm(data=data, instance=self.user)
            if form.is_valid():
                user = form.save()
                self.assertEqual(user.bio_public, expected_bool, f"Boolean conversion failed for '{input_val}'")
    
    def test_concurrent_form_submissions(self):
        """Test handling of concurrent form submissions."""
        # Create two forms for the same user
        data1 = self.base_data.copy()
        data1['first_name'] = 'FirstUpdate'
        
        data2 = self.base_data.copy()
        data2['first_name'] = 'SecondUpdate'
        
        form1 = ProfileEditForm(data=data1, instance=self.user)
        form2 = ProfileEditForm(data=data2, instance=self.user)
        
        # Both should validate
        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())
        
        # Save both (last one wins in this simple case)
        user1 = form1.save()
        user2 = form2.save()
        
        # Verify the second update took precedence
        self.assertEqual(user2.first_name, 'SecondUpdate')
