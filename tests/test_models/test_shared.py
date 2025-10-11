"""
Tests for shared app models and utilities.

This module tests the BaseModel abstract model and shared utilities
used across the CrowdVote application.
"""
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from crowdvote.models import BaseModel
from tests.factories import UserFactory, CommunityFactory


@pytest.mark.models
class TestBaseModel:
    """Test BaseModel abstract model functionality."""
    
    def test_uuid_primary_key_generation(self):
        """Test that BaseModel generates UUID primary keys."""
        community = CommunityFactory()
        
        # Should have UUID primary key
        assert community.id is not None
        assert len(str(community.id)) == 36  # UUID format
        assert '-' in str(community.id)  # UUID contains hyphens
    
    def test_automatic_timestamp_creation(self):
        """Test that created and modified timestamps are set automatically."""
        before_creation = timezone.now()
        community = CommunityFactory()
        after_creation = timezone.now()
        
        # Created timestamp should be set
        assert community.created is not None
        assert before_creation <= community.created <= after_creation
        
        # Modified timestamp should be set  
        assert community.modified is not None
        assert before_creation <= community.modified <= after_creation
        
        # Initially, created and modified should be very close
        time_diff = abs((community.modified - community.created).total_seconds())
        assert time_diff < 1.0  # Less than 1 second difference
    
    def test_automatic_timestamp_updates(self):
        """Test that modified timestamp updates on save."""
        community = CommunityFactory()
        original_created = community.created
        original_modified = community.modified
        
        # Wait a moment then update
        import time
        time.sleep(0.1)
        
        community.name = "Updated Name"
        community.save()
        
        # Created should not change
        assert community.created == original_created
        
        # Modified should be updated
        assert community.modified > original_modified
    
    def test_uuid_uniqueness(self):
        """Test that each model instance gets a unique UUID."""
        community1 = CommunityFactory()
        community2 = CommunityFactory()
        
        assert community1.id != community2.id
        assert str(community1.id) != str(community2.id)
    
    def test_uuid_immutability(self):
        """Test that UUID primary keys cannot be changed after creation."""
        community = CommunityFactory()
        original_id = community.id
        
        # Save again - ID should not change
        community.name = "Updated Name"
        community.save()
        
        assert community.id == original_id
    
    def test_basemodel_inheritance(self):
        """Test that models properly inherit BaseModel functionality."""
        from democracy.models import Community, Decision
        
        # BaseModel-derived models should have UUID primary keys and timestamps
        community = CommunityFactory()
        decision = Decision(
            community=community,
            title="Test Decision",
            description="Test"
        )
        
        # BaseModel models should have UUID primary keys
        assert hasattr(community, 'id')
        assert hasattr(decision, 'id')
        
        # BaseModel models should have timestamps
        assert hasattr(community, 'created')
        assert hasattr(community, 'modified')
        assert hasattr(decision, 'created')
        assert hasattr(decision, 'modified')
        
        # CustomUser uses standard Django User model (not BaseModel)
        # so it has integer primary keys and different timestamp fields
        user = UserFactory()
        assert hasattr(user, 'id')  # Integer PK, not UUID
        assert hasattr(user, 'date_joined')  # Django user timestamp
        assert hasattr(user, 'last_login')   # Django user timestamp


@pytest.mark.models
class TestModelStringRepresentations:
    """Test that all models have proper string representations."""
    
    def test_user_string_representation(self):
        """Test CustomUser string representation."""
        user = UserFactory(username="testuser")
        assert str(user) == "testuser"
        assert repr(user)  # Should not raise
    
    def test_community_string_representation(self):
        """Test Community string representation."""
        community = CommunityFactory(name="Test Community")
        assert str(community) == "Test Community"
        assert repr(community)  # Should not raise
    
    def test_model_meta_properties(self):
        """Test that models have proper meta properties."""
        from democracy.models import Community, Decision, Choice, Ballot, Vote
        from security.models import CustomUser, Following
        
        models = [Community, Decision, Choice, Ballot, Vote, CustomUser, Following]
        
        for model in models:
            # All models should have string representation
            assert hasattr(model, '__str__')
            
            # All models should have proper meta class
            assert hasattr(model, '_meta')
            assert hasattr(model._meta, 'verbose_name')
            assert hasattr(model._meta, 'verbose_name_plural')


@pytest.mark.models
class TestModelValidation:
    """Test general model validation patterns."""
    
    def test_required_field_validation(self):
        """Test that required fields are properly validated."""
        from democracy.models import Community, Decision
        
        # Community requires name
        community = Community()
        with pytest.raises(ValidationError):
            community.full_clean()
        
        # Decision requires title and community
        decision = Decision()
        with pytest.raises(ValidationError):
            decision.full_clean()
    
    def test_field_length_validation(self):
        """Test that field length limits are enforced."""
        community = CommunityFactory()
        
        # Very long name should fail
        community.name = "A" * 300
        with pytest.raises(ValidationError):
            community.full_clean()
    
    def test_foreign_key_validation(self):
        """Test foreign key relationship validation."""
        from democracy.models import Decision
        
        # Decision with invalid community should fail
        decision = Decision(
            title="Test",
            description="Test",
            community_id="invalid-uuid"
        )
        
        with pytest.raises(ValidationError):
            decision.full_clean()


@pytest.mark.models  
class TestModelPerformance:
    """Test model performance and database query patterns."""
    
    def test_bulk_creation_performance(self):
        """Test that bulk operations work efficiently."""
        communities = []
        for i in range(10):
            communities.append(CommunityFactory.build(name=f"Community {i}"))
        
        # Bulk create should work
        from democracy.models import Community
        Community.objects.bulk_create(communities)
        
        # Verify all were created
        assert Community.objects.filter(
            name__startswith="Community"
        ).count() >= 10
    
    def test_model_field_optimization(self):
        """Test that models are optimized for common queries."""
        community = CommunityFactory()
        
        # Models should support efficient filtering
        from democracy.models import Community
        communities = Community.objects.filter(name=community.name)
        assert community in communities
        
        # Models should support efficient ordering
        communities = Community.objects.order_by('created')
        assert len(communities) >= 1
