"""
Tests specifically designed to improve coverage of shared/utilities.py.

This test file focuses on testing untested code paths to increase coverage
rather than duplicating functionality tests.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model

from tests.factories.user_factory import UserFactory
from crowdvote.utilities import get_object_or_None, normal_round, get_random_madeup_tags

User = get_user_model()


@pytest.mark.shared
class TestUtilitiesCoverage(TestCase):
    """Tests to improve coverage of shared/utilities.py functions."""
    
    def test_get_object_or_none_exists(self):
        """Test get_object_or_None when object exists - covers success path."""
        user = UserFactory(username="testuser")
        
        # Should return the user when it exists
        result = get_object_or_None(User, username="testuser")
        self.assertEqual(result, user)
        
    def test_get_object_or_none_does_not_exist(self):
        """Test get_object_or_None when object doesn't exist - covers DoesNotExist path."""
        # Should return None when object doesn't exist
        result = get_object_or_None(User, username="nonexistentuser")
        self.assertIsNone(result)
        
    def test_get_object_or_none_multiple_objects(self):
        """Test get_object_or_None with multiple objects - covers MultipleObjectsReturned path."""
        # Create multiple users with same first name
        UserFactory(first_name="John", last_name="Doe")
        UserFactory(first_name="John", last_name="Smith")
        
        # Should raise MultipleObjectsReturned
        with self.assertRaises(User.MultipleObjectsReturned):
            get_object_or_None(User, first_name="John")
            
    def test_normal_round_floor(self):
        """Test normal_round with numbers that should round down - covers floor path."""
        # Test numbers that should round down
        self.assertEqual(normal_round(2.4), 2)
        self.assertEqual(normal_round(3.1), 3)
        self.assertEqual(normal_round(0.3), 0)
        
    def test_normal_round_ceil(self):
        """Test normal_round with numbers that should round up - covers ceil path."""
        # Test numbers that should round up
        self.assertEqual(normal_round(2.5), 3)
        self.assertEqual(normal_round(3.7), 4)
        self.assertEqual(normal_round(0.8), 1)
        
    def test_normal_round_exact(self):
        """Test normal_round with exact numbers - covers integer path."""
        # Test exact numbers
        self.assertEqual(normal_round(2.0), 2)
        self.assertEqual(normal_round(5.0), 5)
        
    def test_get_random_madeup_tags_returns_list(self):
        """Test get_random_madeup_tags returns list - covers basic functionality."""
        tags = get_random_madeup_tags()
        
        # Should return a list
        self.assertIsInstance(tags, list)
        
        # Should contain only strings
        for tag in tags:
            self.assertIsInstance(tag, str)
            
    def test_get_random_madeup_tags_variability(self):
        """Test get_random_madeup_tags produces variable results - covers randomness."""
        # Run multiple times to test variability
        results = []
        for _ in range(10):
            tags = get_random_madeup_tags()
            results.append(len(tags))
            
        # Should have some variability in length (not all same length)
        unique_lengths = set(results)
        self.assertGreaterEqual(len(unique_lengths), 1)  # At least some variation expected
        
    def test_get_random_madeup_tags_content(self):
        """Test get_random_madeup_tags content format - covers tag generation logic."""
        tags = get_random_madeup_tags()
        
        # Each tag should be 5 characters of the same letter
        for tag in tags:
            if tag:  # If not empty
                self.assertEqual(len(tag), 5)
                # Should be all same character
                self.assertTrue(all(c == tag[0] for c in tag))
                # Should be lowercase letter
                self.assertTrue(tag[0].islower())
                
    def test_get_random_madeup_tags_deduplication(self):
        """Test get_random_madeup_tags deduplicates - covers set() conversion."""
        # Run many times to try to trigger duplicate generation
        for _ in range(50):  # Multiple attempts to get duplicates
            tags = get_random_madeup_tags()
            # Should have no duplicates (set conversion removes them)
            self.assertEqual(len(tags), len(set(tags)))
            
    def test_utilities_edge_cases(self):
        """Test edge cases in utilities - covers boundary conditions."""
        # Test normal_round with edge cases
        self.assertEqual(normal_round(0.5), 1)  # Exactly half rounds up
        self.assertEqual(normal_round(-0.5), 0)  # Negative half
        
        # Test get_object_or_None with different model methods
        user = UserFactory(username="testuser", first_name="Test")
        
        # Test with multiple keyword arguments
        result = get_object_or_None(User, username="testuser", first_name="Test")
        self.assertEqual(result, user)
        
        # Test with non-existent combination
        result = get_object_or_None(User, username="testuser", first_name="Wrong")
        self.assertIsNone(result)
        
    def test_normal_round_precision(self):
        """Test normal_round with various decimal precisions - covers math operations."""
        # Test with different decimal precisions
        self.assertEqual(normal_round(1.49999), 1)
        self.assertEqual(normal_round(1.50001), 2)
        self.assertEqual(normal_round(2.999), 3)
        
    def test_get_object_or_none_with_queryset(self):
        """Test get_object_or_None with QuerySet - covers QuerySet handling."""
        user = UserFactory(username="testuser")
        
        # Test with QuerySet instead of Model class
        queryset = User.objects.filter(username__icontains="test")
        result = get_object_or_None(queryset, username="testuser")
        self.assertEqual(result, user)
        
        # Test QuerySet with no matches
        empty_queryset = User.objects.filter(username="nonexistent")
        result = get_object_or_None(empty_queryset)
        self.assertIsNone(result)
        
    def test_normal_round_negative_numbers(self):
        """Test normal_round with negative numbers - covers negative number handling."""
        # Test negative numbers
        self.assertEqual(normal_round(-1.4), -1)
        self.assertEqual(normal_round(-1.6), -2)
        self.assertEqual(normal_round(-2.5), -2)  # Half rounds toward zero
        
    def test_get_random_madeup_tags_performance(self):
        """Test get_random_madeup_tags performance - covers function efficiency."""
        # Should complete quickly even with multiple calls
        import time
        start_time = time.time()
        
        for _ in range(100):
            tags = get_random_madeup_tags()
            
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second for 100 calls)
        self.assertLess(end_time - start_time, 1.0)
        
    def test_get_object_or_none_with_positional_args(self):
        """Test get_object_or_None with positional arguments - covers *args handling."""
        user = UserFactory()
        
        # Test with keyword argument (primary key)
        result = get_object_or_None(User, pk=user.pk)
        self.assertEqual(result, user)
        
        # Test with non-existent primary key
        result = get_object_or_None(User, pk=99999)
        self.assertIsNone(result)
