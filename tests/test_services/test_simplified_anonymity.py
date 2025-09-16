"""
Tests for Plan #23: Simplified Anonymity System with Hashed Usernames.

This module tests the new anonymity system that replaces AnonymousVoteMapping
with hashed usernames stored directly on the Ballot model.
"""

import pytest
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from democracy.utils import generate_username_hash, verify_username_hash
from democracy.models import Community, Decision, Ballot, Choice, Vote, Membership

User = get_user_model()


class HashGenerationTest(TestCase):
    """Test hash generation and verification functions."""
    
    def test_generate_username_hash(self):
        """Test that hash generation produces consistent results."""
        username = "testuser"
        hash1 = generate_username_hash(username)
        hash2 = generate_username_hash(username)
        
        # Same username should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Hash should be 64 characters (SHA-256 hex)
        self.assertEqual(len(hash1), 64)
        
        # Hash should be hexadecimal
        self.assertTrue(all(c in '0123456789abcdef' for c in hash1))
    
    def test_different_usernames_different_hashes(self):
        """Test that different usernames produce different hashes."""
        hash1 = generate_username_hash("user1")
        hash2 = generate_username_hash("user2")
        
        self.assertNotEqual(hash1, hash2)
    
    def test_verify_username_hash(self):
        """Test hash verification function."""
        username = "testuser"
        correct_hash = generate_username_hash(username)
        wrong_hash = generate_username_hash("wronguser")
        
        # Correct username should verify
        self.assertTrue(verify_username_hash(username, correct_hash))
        
        # Wrong username should not verify
        self.assertFalse(verify_username_hash(username, wrong_hash))
    
    @override_settings(ANONYMITY_SALT='test-salt-123')
    def test_salt_affects_hash(self):
        """Test that different salts produce different hashes."""
        username = "testuser"
        
        # Generate hash with test salt
        hash_with_test_salt = generate_username_hash(username)
        
        # Change salt and generate again
        with override_settings(ANONYMITY_SALT='different-salt-456'):
            hash_with_different_salt = generate_username_hash(username)
        
        # Hashes should be different
        self.assertNotEqual(hash_with_test_salt, hash_with_different_salt)


class BallotAnonymityTest(TestCase):
    """Test ballot creation and anonymity handling."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.community = Community.objects.create(
            name='Test Community',
            description='A test community'
        )
        self.membership = Membership.objects.create(
            member=self.user,
            community=self.community,
            is_voting_community_member=True
        )
        self.decision = Decision.objects.create(
            title='Test Decision',
            description='A test decision',
            community=self.community,
            dt_close='2025-12-31 23:59:59+00:00'
        )
        self.choice = Choice.objects.create(
            decision=self.decision,
            title='Test Choice',
            description='A test choice'
        )
    
    def test_ballot_creation_with_hash(self):
        """Test that ballots are created with hashed usernames."""
        ballot = Ballot.objects.create(
            decision=self.decision,
            voter=self.user,
            is_anonymous=True,
            hashed_username=generate_username_hash(self.user.username)
        )
        
        # Hash should be populated
        self.assertIsNotNone(ballot.hashed_username)
        self.assertEqual(len(ballot.hashed_username), 64)
        
        # Hash should verify against username
        self.assertTrue(verify_username_hash(self.user.username, ballot.hashed_username))
    
    def test_ballot_display_name_anonymous(self):
        """Test ballot display name for anonymous votes."""
        ballot = Ballot.objects.create(
            decision=self.decision,
            voter=self.user,
            is_anonymous=True,
            hashed_username=generate_username_hash(self.user.username)
        )
        
        # Anonymous ballot should display "Anonymous"
        self.assertEqual(ballot.get_display_name(), "Anonymous")
        self.assertEqual(ballot.get_display_username(), "Anonymous")
    
    def test_ballot_display_name_public(self):
        """Test ballot display name for public votes."""
        ballot = Ballot.objects.create(
            decision=self.decision,
            voter=self.user,
            is_anonymous=False,
            hashed_username=generate_username_hash(self.user.username)
        )
        
        # Public ballot should display actual username
        self.assertEqual(ballot.get_display_name(), self.user.username)
        self.assertEqual(ballot.get_display_username(), self.user.username)
    
    def test_user_default_anonymity_preference(self):
        """Test user's default anonymity preference."""
        # Default should be False
        self.assertFalse(self.user.vote_anonymously_by_default)
        
        # Should be able to change it
        self.user.vote_anonymously_by_default = True
        self.user.save()
        self.user.refresh_from_db()
        self.assertTrue(self.user.vote_anonymously_by_default)


class AnonymityIntegrationTest(TestCase):
    """Test integration of anonymity system with voting workflow."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            vote_anonymously_by_default=False
        )
        self.user2 = User.objects.create_user(
            username='user2', 
            email='user2@example.com',
            vote_anonymously_by_default=True
        )
        self.community = Community.objects.create(
            name='Test Community',
            description='A test community'
        )
        
        # Create memberships
        for user in [self.user1, self.user2]:
            Membership.objects.create(
                member=user,
                community=self.community,
                is_voting_community_member=True
            )
        
        self.decision = Decision.objects.create(
            title='Test Decision',
            description='A test decision',
            community=self.community,
            dt_close='2025-12-31 23:59:59+00:00'
        )
        
        # Create choices
        self.choice1 = Choice.objects.create(
            decision=self.decision,
            title='Choice 1',
            description='First choice'
        )
        self.choice2 = Choice.objects.create(
            decision=self.decision,
            title='Choice 2', 
            description='Second choice'
        )
    
    def test_mixed_anonymity_ballots(self):
        """Test that some ballots can be anonymous while others are public."""
        # Create public ballot for user1
        ballot1 = Ballot.objects.create(
            decision=self.decision,
            voter=self.user1,
            is_anonymous=False,
            hashed_username=generate_username_hash(self.user1.username)
        )
        
        # Create anonymous ballot for user2
        ballot2 = Ballot.objects.create(
            decision=self.decision,
            voter=self.user2,
            is_anonymous=True,
            hashed_username=generate_username_hash(self.user2.username)
        )
        
        # Check display names
        self.assertEqual(ballot1.get_display_name(), 'user1')
        self.assertEqual(ballot2.get_display_name(), 'Anonymous')
        
        # Both should have valid hashes
        self.assertTrue(verify_username_hash('user1', ballot1.hashed_username))
        self.assertTrue(verify_username_hash('user2', ballot2.hashed_username))
        
        # Hashes should be different
        self.assertNotEqual(ballot1.hashed_username, ballot2.hashed_username)
    
    def test_ballot_hash_consistency(self):
        """Test that ballot hashes remain consistent for the same user."""
        # Create multiple ballots for same user
        ballot1 = Ballot.objects.create(
            decision=self.decision,
            voter=self.user1,
            is_anonymous=True,
            hashed_username=generate_username_hash(self.user1.username)
        )
        
        # Create another decision and ballot
        decision2 = Decision.objects.create(
            title='Another Decision',
            description='Another test decision',
            community=self.community,
            dt_close='2025-12-31 23:59:59+00:00'
        )
        
        ballot2 = Ballot.objects.create(
            decision=decision2,
            voter=self.user1,
            is_anonymous=True,
            hashed_username=generate_username_hash(self.user1.username)
        )
        
        # Hashes should be identical (same user, same salt)
        self.assertEqual(ballot1.hashed_username, ballot2.hashed_username)
        
        # Both should verify against the same username
        self.assertTrue(verify_username_hash(self.user1.username, ballot1.hashed_username))
        self.assertTrue(verify_username_hash(self.user1.username, ballot2.hashed_username))


class SecurityTest(TestCase):
    """Test security aspects of the anonymity system."""
    
    def test_hash_irreversibility(self):
        """Test that hashes cannot be easily reversed."""
        username = "secretuser"
        hash_value = generate_username_hash(username)
        
        # Hash should not contain the original username
        self.assertNotIn(username, hash_value)
        self.assertNotIn(username.upper(), hash_value.upper())
        
        # Hash should be deterministic but not obvious
        self.assertEqual(hash_value, generate_username_hash(username))
        self.assertNotEqual(hash_value, generate_username_hash(username + "x"))
    
    @override_settings(ANONYMITY_SALT='')
    def test_empty_salt_still_works(self):
        """Test that system works even with empty salt (though not recommended)."""
        username = "testuser"
        hash_value = generate_username_hash(username)
        
        # Should still produce a valid hash
        self.assertEqual(len(hash_value), 64)
        self.assertTrue(verify_username_hash(username, hash_value))
    
    def test_salt_independence(self):
        """Test that different salts produce independent hash spaces."""
        username = "testuser"
        
        with override_settings(ANONYMITY_SALT='salt1'):
            hash1 = generate_username_hash(username)
        
        with override_settings(ANONYMITY_SALT='salt2'):
            hash2 = generate_username_hash(username)
        
        # Same username with different salts should produce different hashes
        self.assertNotEqual(hash1, hash2)
        
        # Each hash should verify only with its corresponding salt
        with override_settings(ANONYMITY_SALT='salt1'):
            self.assertTrue(verify_username_hash(username, hash1))
            self.assertFalse(verify_username_hash(username, hash2))
        
        with override_settings(ANONYMITY_SALT='salt2'):
            self.assertFalse(verify_username_hash(username, hash1))
            self.assertTrue(verify_username_hash(username, hash2))
