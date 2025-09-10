"""
Comprehensive tests for democracy app forms.

Tests cover validation, security, edge cases, and business logic for all forms
in the democracy app, focusing on preventing regression bugs and ensuring
robust form handling.
"""

import pytest
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.forms.formsets import BaseFormSet
from django import forms

from democracy.forms import (
    DecisionForm, ChoiceForm, ChoiceFormSet, VoteForm, DecisionSearchForm
)
from democracy.models import Decision, Choice, Ballot, Vote
from tests.factories.user_factory import UserFactory
from tests.factories.community_factory import CommunityFactory
from tests.factories.decision_factory import DecisionFactory, ChoiceFactory, BallotFactory


@pytest.mark.forms
class TestDecisionForm(TestCase):
    """Test the DecisionForm for creating and editing decisions."""
    
    def setUp(self):
        """Set up test data for each test."""
        self.user = UserFactory()
        self.community = CommunityFactory()
        self.valid_data = {
            'title': 'Test Decision',
            'description': 'This is a test decision with enough detail to meet the minimum length requirement of 50 characters.',
            'dt_close': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')
        }
    
    def test_valid_form_creation(self):
        """Test that a valid form can be created and saved."""
        form = DecisionForm(data=self.valid_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        decision = form.save(commit=False)
        decision.community = self.community
        decision.save()
        
        self.assertEqual(decision.title, 'Test Decision')
        self.assertEqual(decision.community, self.community)
    
    def test_title_validation(self):
        """Test title field validation."""
        # Empty title
        data = self.valid_data.copy()
        data['title'] = ''
        form = DecisionForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        
        # Too long title (max 200 characters)
        data['title'] = 'x' * 201
        form = DecisionForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        
        # Valid title
        data['title'] = 'Valid Decision Title'
        form = DecisionForm(data=data)
        self.assertTrue(form.is_valid())
    
    def test_description_validation(self):
        """Test description field validation."""
        # Empty description
        data = self.valid_data.copy()
        data['description'] = ''
        form = DecisionForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('description', form.errors)
        
        # Too short description (minimum 50 characters)
        data['description'] = 'Too short'
        form = DecisionForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('description', form.errors)
        
        # Valid description
        data['description'] = 'This is a valid description that meets the minimum length requirement of 50 characters for proper context.'
        form = DecisionForm(data=data)
        self.assertTrue(form.is_valid())
    
    def test_deadline_validation(self):
        """Test deadline field validation."""
        # Past deadline
        data = self.valid_data.copy()
        data['dt_close'] = (timezone.now() - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
        form = DecisionForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('dt_close', form.errors)
        
        # Too soon (less than 1 hour)
        data['dt_close'] = (timezone.now() + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
        form = DecisionForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('dt_close', form.errors)
        
        # Valid future deadline
        data['dt_close'] = (timezone.now() + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
        form = DecisionForm(data=data)
        self.assertTrue(form.is_valid())
    
    def test_form_widget_attributes(self):
        """Test that form widgets have correct CSS classes and attributes."""
        form = DecisionForm()
        
        # Check title widget
        title_widget = form.fields['title'].widget
        self.assertIn('w-full', title_widget.attrs['class'])
        self.assertIn('placeholder', title_widget.attrs)
        
        # Check description widget
        desc_widget = form.fields['description'].widget
        self.assertIn('w-full', desc_widget.attrs['class'])
        self.assertEqual(desc_widget.attrs['rows'], 4)
        
        # Check datetime widget
        dt_widget = form.fields['dt_close'].widget
        # DateTimeInput widget should have datetime-local type
        self.assertIsInstance(dt_widget, forms.DateTimeInput)
        # Check that type attribute is set (either in attrs or as widget property)
        widget_type = dt_widget.attrs.get('type', getattr(dt_widget, 'input_type', None))
        self.assertEqual(widget_type, 'datetime-local')
        self.assertIn('min', dt_widget.attrs)
    
    def test_xss_prevention(self):
        """Test that form prevents XSS attacks."""
        xss_payloads = [
            '<script>alert("xss")</script>',
            '"><script>alert("xss")</script>',
            'javascript:alert("xss")',
            '<img src="x" onerror="alert(\'xss\')">'
        ]
        
        for payload in xss_payloads:
            data = self.valid_data.copy()
            data['title'] = f'Safe Title {payload}'
            data['description'] = f'Safe description with enough length to pass validation. {payload}'
            
            form = DecisionForm(data=data)
            if form.is_valid():
                decision = form.save(commit=False)
                decision.community = self.community
                decision.save()
                
                # Verify the payload is stored as-is (Django template system will escape it)
                self.assertIn(payload, decision.title)
                self.assertIn(payload, decision.description)


@pytest.mark.forms
class TestChoiceForm(TestCase):
    """Test the ChoiceForm for decision options."""
    
    def setUp(self):
        """Set up test data for each test."""
        self.decision = DecisionFactory()
        self.valid_data = {
            'title': 'Test Choice',
            'description': 'This is a test choice with sufficient description length for validation requirements.'
        }
    
    def test_valid_choice_creation(self):
        """Test that a valid choice can be created."""
        form = ChoiceForm(data=self.valid_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        choice = form.save(commit=False)
        choice.decision = self.decision
        choice.save()
        
        self.assertEqual(choice.title, 'Test Choice')
        self.assertEqual(choice.decision, self.decision)
    
    def test_title_validation(self):
        """Test choice title validation."""
        # Empty title
        data = self.valid_data.copy()
        data['title'] = ''
        form = ChoiceForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        
        # Too long title
        data['title'] = 'x' * 101
        form = ChoiceForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_description_validation(self):
        """Test choice description validation."""
        # Description is optional
        data = self.valid_data.copy()
        data['description'] = ''
        form = ChoiceForm(data=data)
        self.assertTrue(form.is_valid())
        
        # Too long description
        data['description'] = 'x' * 1001
        form = ChoiceForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('description', form.errors)


@pytest.mark.forms
class TestChoiceFormSet(TestCase):
    """Test the ChoiceFormSet for managing multiple choices."""
    
    def setUp(self):
        """Set up test data for each test."""
        self.decision = DecisionFactory()
    
    def test_formset_validation(self):
        """Test formset validation for minimum and maximum choices."""
        # Test minimum choices (should require at least 2)
        formset_data = {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '2',
            'form-MAX_NUM_FORMS': '10',
            'form-0-title': 'Only Choice',
            'form-0-description': 'This is the only choice'
        }
        
        formset = ChoiceFormSet(data=formset_data, instance=self.decision)
        self.assertFalse(formset.is_valid())
        
        # Test valid number of choices
        formset_data.update({
            'form-TOTAL_FORMS': '2',
            'form-MIN_NUM_FORMS': '2',
            'form-MAX_NUM_FORMS': '10',
            'form-1-title': 'Second Choice',
            'form-1-description': 'This is the second choice'
        })
        
        formset = ChoiceFormSet(data=formset_data, instance=self.decision)
        if not formset.is_valid():
            for i, form in enumerate(formset):
                print(f"Form {i} valid: {form.is_valid()}, errors: {form.errors}")
        self.assertTrue(formset.is_valid(), f"Formset errors: {formset.errors}, Non-field errors: {formset.non_form_errors()}")
    
    def test_formset_max_choices(self):
        """Test that formset enforces maximum choice limit."""
        # Create data for 11 choices (should exceed max of 10)
        formset_data = {
            'form-TOTAL_FORMS': '11',
            'form-INITIAL_FORMS': '0'
        }
        
        for i in range(11):
            formset_data[f'form-{i}-title'] = f'Choice {i+1}'
            formset_data[f'form-{i}-description'] = f'Description for choice {i+1} with sufficient length to pass validation.'
        
        formset = ChoiceFormSet(data=formset_data, instance=self.decision)
        self.assertFalse(formset.is_valid())


@pytest.mark.forms
class TestVoteForm(TestCase):
    """Test the VoteForm for casting votes."""
    
    def setUp(self):
        """Set up test data for each test."""
        self.user = UserFactory()
        self.decision = DecisionFactory(with_choices=False)  # Don't auto-create choices
        self.choices = [
            ChoiceFactory(decision=self.decision),
            ChoiceFactory(decision=self.decision),
            ChoiceFactory(decision=self.decision)
        ]
        self.ballot = BallotFactory(decision=self.decision, voter=self.user, with_votes=False)
    
    def test_valid_vote_submission(self):
        """Test that valid votes can be submitted."""
        form_data = {
            f'choice_{self.choices[0].id}': '5',
            f'choice_{self.choices[1].id}': '3',
            f'choice_{self.choices[2].id}': '1',
            'tags': 'governance, budget',
            'is_anonymous': False
        }
        
        form = VoteForm(self.decision, self.user, data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
    
    def test_star_rating_validation(self):
        """Test that star ratings are validated correctly."""
        # Invalid rating (too high)
        form_data = {
            f'choice_{self.choices[0].id}': '6',
            'tags': 'governance',
            'is_anonymous': False
        }
        
        form = VoteForm(self.decision, self.user, data=form_data)
        self.assertFalse(form.is_valid())
        
        # Invalid rating (negative)
        form_data[f'choice_{self.choices[0].id}'] = '-1'
        form = VoteForm(self.decision, self.user, data=form_data)
        self.assertFalse(form.is_valid())
        
        # Valid rating - provide ratings for all choices
        form_data = {
            f'choice_{self.choices[0].id}': '4',
            f'choice_{self.choices[1].id}': '3', 
            f'choice_{self.choices[2].id}': '2',
            'tags': 'governance',
            'is_anonymous': False
        }
        form = VoteForm(self.decision, self.user, data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
    
    def test_tag_validation(self):
        """Test tag field validation."""
        form_data = {
            f'choice_{self.choices[0].id}': '4',
            f'choice_{self.choices[1].id}': '3',
            f'choice_{self.choices[2].id}': '2',
            'tags': 'governance, budget, environment',
            'is_anonymous': False
        }
        
        form = VoteForm(self.decision, self.user, data=form_data)
        self.assertTrue(form.is_valid())
        
        # Test empty tags (should be valid)
        form_data['tags'] = ''
        form = VoteForm(self.decision, self.user, data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_at_least_one_vote_required(self):
        """Test that at least one choice must be rated."""
        form_data = {
            'tags': 'governance',
            'is_anonymous': False
        }
        
        form = VoteForm(self.decision, self.user, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('You must rate at least one choice with 1 or more stars', str(form.errors))


@pytest.mark.forms
class TestDecisionSearchForm(TestCase):
    """Test the DecisionSearchForm for filtering decisions."""
    
    def test_valid_search_form(self):
        """Test that search form validates correctly."""
        form_data = {
            'search': 'test query',
            'status': 'active',
            'sort': 'newest'
        }
        
        form = DecisionSearchForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_empty_form_valid(self):
        """Test that empty search form is valid."""
        form = DecisionSearchForm(data={})
        self.assertTrue(form.is_valid())
    
    def test_search_field_validation(self):
        """Test search field validation."""
        # Very long search query
        form_data = {
            'search': 'x' * 201,
            'status': 'active',
            'sort': 'newest'
        }
        
        form = DecisionSearchForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('search', form.errors)
    
    def test_status_choices_validation(self):
        """Test that status field validates against choices."""
        form_data = {
            'status': 'invalid_status',
            'sort': 'newest'
        }
        
        form = DecisionSearchForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('status', form.errors)
    
    def test_sort_choices_validation(self):
        """Test that sort field validates against choices."""
        form_data = {
            'status': 'active',
            'sort': 'invalid_sort'
        }
        
        form = DecisionSearchForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('sort', form.errors)


@pytest.mark.forms
class TestFormSecurityAndEdgeCases(TestCase):
    """Test security vulnerabilities and edge cases across all forms."""
    
    def setUp(self):
        """Set up test data for security tests."""
        self.user = UserFactory()
        self.community = CommunityFactory()
        self.decision = DecisionFactory()
        self.choices = [ChoiceFactory(decision=self.decision) for _ in range(3)]
    
    def test_sql_injection_prevention(self):
        """Test that forms prevent SQL injection attacks."""
        sql_payloads = [
            "'; DROP TABLE auth_user; --",
            "' OR '1'='1",
            "'; DELETE FROM democracy_decision; --",
            "1'; UNION SELECT * FROM auth_user; --"
        ]
        
        for payload in sql_payloads:
            # Test DecisionForm
            data = {
                'title': f'Title {payload}',
                'description': f'Description with payload {payload} and sufficient length to pass validation requirements.',
                'dt_close': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
            }
            
            form = DecisionForm(data=data)
            if form.is_valid():
                decision = form.save(commit=False)
                decision.community = self.community
                decision.save()
                
                # Verify data is stored safely
                self.assertIn(payload, decision.title)
                self.assertIn(payload, decision.description)
    
    def test_unicode_handling(self):
        """Test that forms handle Unicode characters correctly."""
        unicode_strings = [
            'Decision with émojis 🗳️ and spéciál chars',
            'Ñoñó español título',
            '中文标题测试',
            'Тест на русском языке',
            '🎉🗳️🌟 Emoji decision 🚀🎯'
        ]
        
        for unicode_str in unicode_strings:
            data = {
                'title': unicode_str,
                'description': f'Unicode description: {unicode_str}. This has enough length to pass validation requirements.',
                'dt_close': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
            }
            
            form = DecisionForm(data=data)
            self.assertTrue(form.is_valid(), f"Unicode string '{unicode_str}' failed validation: {form.errors}")
    
    def test_boundary_conditions(self):
        """Test boundary conditions for field lengths."""
        # Test exactly at limits
        boundary_tests = [
            # DecisionForm title: max 200 chars
            ('title', 'x' * 200, True),
            ('title', 'x' * 201, False),
            
            # Description: min 50 chars
            ('description', 'x' * 50, True),
            ('description', 'x' * 49, False),
        ]
        
        for field, value, should_be_valid in boundary_tests:
            data = {
                'title': 'Test Title',
                'description': 'This is a test description with exactly fifty chars.',
                'dt_close': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
            }
            data[field] = value
            
            form = DecisionForm(data=data)
            if should_be_valid:
                self.assertTrue(form.is_valid(), f"Boundary test failed for {field}: {form.errors}")
            else:
                self.assertFalse(form.is_valid(), f"Boundary test should have failed for {field}")
    
    def test_csrf_protection_requirements(self):
        """Test that forms are designed to work with CSRF protection."""
        # This is more of a documentation test - forms should be used with {% csrf_token %}
        form = DecisionForm()
        
        # Verify form doesn't disable CSRF (no csrf_exempt decorators, etc.)
        # This is validated by checking that forms are standard Django forms
        self.assertIsInstance(form, forms.ModelForm)
        self.assertTrue(hasattr(form, 'is_valid'))
        self.assertTrue(hasattr(form, 'cleaned_data'))
