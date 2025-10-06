# Plan #23: Simplified Anonymity System with Hashed Usernames

## Overview

Replace the current `AnonymousVoteMapping` table-based anonymity system with a simplified approach using one-way hashed usernames stored directly on the `Ballot` model. This eliminates the complexity of maintaining a secure mapping table while providing robust privacy protection through cryptographic hashing.

## Current System Issues

The existing `AnonymousVoteMapping` model creates several maintenance and security challenges:

1. **Complex Database Architecture**: Requires a separate secure table with strict access controls
2. **Mapping Table Management**: Need to manage GUID generation and cleanup
3. **Security Surface Area**: Additional table that must be protected and encrypted
4. **Performance Overhead**: Extra joins and lookups for anonymous vote display
5. **Deployment Complexity**: Requires special database-level encryption configuration

## Proposed Solution: Hashed Username Approach

### Core Concept

Instead of maintaining a mapping table, store a one-way hash of the member's username directly on the `Ballot` model. The system will:

- **For Anonymous Votes**: Display only "Anonymous" in public interfaces
- **For Public Votes**: Display the actual member username
- **For Verification**: Use the hash to verify vote authenticity without revealing identity

### Security Model

```python
# Environment variable (kept secret)
ANONYMITY_SALT = "your-secret-salt-here"

# One-way hash generation
import hashlib
hashed_username = hashlib.sha256(f"{username}{ANONYMITY_SALT}".encode()).hexdigest()
```

**Security Benefits**:
- **One-way function**: Cannot reverse the hash to get the username
- **Salt protection**: Even with database access, usernames cannot be determined without the salt
- **No mapping table**: Eliminates the most sensitive part of the current system
- **Simple verification**: Can verify a vote belongs to a specific user without exposing identity

## Implementation Plan

### Phase 1: Database Schema Changes

#### 1.1 Add Fields to Ballot Model

```python
# democracy/models.py - Ballot model additions
class Ballot(BaseModel):
    # ... existing fields ...
    
    # New anonymity fields
    hashed_username = models.CharField(
        max_length=64,  # SHA-256 produces 64-character hex string
        help_text="One-way hash of the voter's username for verification"
    )
    
    # Keep existing is_anonymous field for display logic
    is_anonymous = models.BooleanField(
        default=False,
        help_text="Whether this ballot should be displayed anonymously"
    )
```

#### 1.2 Add User Profile Default

```python
# accounts/models.py - CustomUser model addition
class CustomUser(AbstractUser):
    # ... existing fields ...
    
    vote_anonymously_by_default = models.BooleanField(
        default=False,
        help_text="Default anonymity preference for new votes"
    )
```

### Phase 2: Utility Functions

#### 2.1 Hash Generation Utility

```python
# accounts/utils.py or democracy/utils.py
import hashlib
from django.conf import settings

def generate_username_hash(username):
    """
    Generate a one-way hash of the username for anonymity verification.
    
    Args:
        username (str): The username to hash
        
    Returns:
        str: 64-character SHA-256 hash
    """
    salt = settings.ANONYMITY_SALT
    return hashlib.sha256(f"{username}{salt}".encode()).hexdigest()

def verify_username_hash(username, hash_to_check):
    """
    Verify that a hash corresponds to a given username.
    
    Args:
        username (str): The username to verify
        hash_to_check (str): The hash to verify against
        
    Returns:
        bool: True if hash matches username
    """
    return generate_username_hash(username) == hash_to_check
```

#### 2.2 Display Logic Helper

```python
# democracy/models.py - Ballot model method
def get_display_username(self):
    """
    Get the username to display for this ballot.
    
    Returns:
        str: Either the actual username or "Anonymous"
    """
    if self.is_anonymous:
        return "Anonymous"
    else:
        return self.voter.username
```

### Phase 3: Settings Configuration

#### 3.1 Environment Variable

```python
# crowdvote/settings.py
ANONYMITY_SALT = env('ANONYMITY_SALT', default='development-salt-change-in-production')
```

#### 3.2 Production Environment

```bash
# .env or Railway environment variables
ANONYMITY_SALT=your-very-secure-random-salt-string-here
```

### Phase 4: Migration Strategy

#### 4.1 Database Migration

```python
# democracy/migrations/0015_add_hashed_username_anonymity.py
from django.db import migrations, models
from democracy.utils import generate_username_hash

def populate_hashed_usernames(apps, schema_editor):
    """Populate hashed_username field for existing ballots."""
    Ballot = apps.get_model('democracy', 'Ballot')
    
    for ballot in Ballot.objects.select_related('voter').all():
        ballot.hashed_username = generate_username_hash(ballot.voter.username)
        ballot.save(update_fields=['hashed_username'])

def reverse_populate_hashed_usernames(apps, schema_editor):
    """Reverse migration - clear hashed usernames."""
    Ballot = apps.get_model('democracy', 'Ballot')
    Ballot.objects.update(hashed_username='')

class Migration(migrations.Migration):
    dependencies = [
        ('democracy', '0014_fix_snapshot_blank_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='ballot',
            name='hashed_username',
            field=models.CharField(default='', max_length=64, help_text="One-way hash of the voter's username for verification"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='customuser',
            name='vote_anonymously_by_default',
            field=models.BooleanField(default=False, help_text="Default anonymity preference for new votes"),
        ),
        migrations.RunPython(
            populate_hashed_usernames,
            reverse_populate_hashed_usernames
        ),
        migrations.AlterField(
            model_name='ballot',
            name='hashed_username',
            field=models.CharField(max_length=64, help_text="One-way hash of the voter's username for verification"),
        ),
    ]
```

### Phase 5: Update Ballot Creation Logic

#### 5.1 Voting Views

```python
# democracy/views.py - vote_submit view updates
def vote_submit(request, community_id, decision_id):
    # ... existing logic ...
    
    # Determine anonymity preference
    user_default = request.user.vote_anonymously_by_default
    is_anonymous = request.POST.get('is_anonymous', user_default)
    
    # Create ballot with hashed username
    ballot = Ballot.objects.create(
        decision=decision,
        voter=request.user,
        is_anonymous=is_anonymous,
        hashed_username=generate_username_hash(request.user.username),
        # ... other fields ...
    )
```

#### 5.2 Calculated Ballot Creation

```python
# democracy/services.py - StageBallots service updates
def create_calculated_ballot(self, decision, voter, inherited_votes, tags):
    """Create a calculated ballot with proper anonymity handling."""
    
    # Use voter's default anonymity preference for calculated ballots
    is_anonymous = voter.vote_anonymously_by_default
    
    ballot = Ballot.objects.create(
        decision=decision,
        voter=voter,
        is_calculated=True,
        is_anonymous=is_anonymous,
        hashed_username=generate_username_hash(voter.username),
        tags=tags,
    )
    
    # ... rest of ballot creation logic ...
```

### Phase 6: Update Display Logic

#### 6.1 Template Updates

```html
<!-- democracy/templates/democracy/decision_results.html -->
<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
    {{ ballot.get_display_username }}
</td>
```

#### 6.2 Delegation Tree Updates

```python
# democracy/tree_service.py - DelegationTreeService updates
def format_username(self, user, ballot=None):
    """Format username for display in delegation trees."""
    if ballot and ballot.is_anonymous:
        return "Anonymous"
    else:
        return user.username
```

### Phase 7: Remove AnonymousVoteMapping

#### 7.1 Model Removal

```python
# democracy/models.py - Remove AnonymousVoteMapping class entirely
# This will be done in a separate migration after the new system is working
```

#### 7.2 Cleanup Migration

```python
# democracy/migrations/0016_remove_anonymous_vote_mapping.py
class Migration(migrations.Migration):
    dependencies = [
        ('democracy', '0015_add_hashed_username_anonymity'),
    ]

    operations = [
        migrations.DeleteModel(
            name='AnonymousVoteMapping',
        ),
    ]
```

## Files Requiring Updates

### Models and Database
- `democracy/models.py` - Remove AnonymousVoteMapping, update Ballot model
- `accounts/models.py` - Add vote_anonymously_by_default field
- `democracy/migrations/` - Two new migrations for the transition

### Services and Business Logic
- `democracy/services.py` - Update StageBallots service for calculated ballots
- `democracy/utils.py` - Add hash generation and verification functions
- `democracy/views.py` - Update vote_submit view
- `democracy/tree_service.py` - Update username display logic

### Templates and UI
- `democracy/templates/democracy/decision_results.html` - Update vote tally display
- `democracy/templates/democracy/decision_detail.html` - Update voting form
- `democracy/templates/democracy/components/delegation_tree.html` - Update tree display
- `accounts/templates/accounts/profile_setup.html` - Add anonymity preference
- `accounts/templates/accounts/edit_profile.html` - Add anonymity preference

### Forms and Views
- `democracy/forms.py` - Update VoteForm to include anonymity toggle
- `accounts/forms.py` - Update ProfileForm for anonymity preference
- `accounts/views.py` - Update profile views

### Admin Interface
- `democracy/admin.py` - Remove AnonymousVoteMapping admin, update Ballot admin
- `accounts/admin.py` - Update CustomUser admin

### Settings and Configuration
- `crowdvote/settings.py` - Add ANONYMITY_SALT configuration
- Environment variable documentation updates

### Tests
- Update all tests that reference AnonymousVoteMapping
- Add tests for hash generation and verification
- Update ballot creation tests
- Update display logic tests

## Testing Strategy

### Unit Tests
1. **Hash Generation**: Test hash generation and verification functions
2. **Ballot Creation**: Test ballot creation with anonymity preferences
3. **Display Logic**: Test username display logic for anonymous vs public votes
4. **Migration**: Test data migration from old to new system

### Integration Tests
1. **Voting Flow**: Test complete voting flow with anonymity preferences
2. **Delegation Trees**: Test delegation tree display with anonymous votes
3. **Results Display**: Test decision results with mixed anonymous/public votes

### Security Tests
1. **Hash Verification**: Verify hashes cannot be reversed without salt
2. **Salt Protection**: Test that changing salt invalidates existing hashes
3. **Privacy Protection**: Verify anonymous votes don't leak usernames

## Deployment Considerations

### Environment Variables
- **ANONYMITY_SALT**: Must be set in production environment
- **Salt Rotation**: Plan for potential salt rotation in the future

### Database Migration
- **Downtime**: Migration may require brief downtime for hash population
- **Rollback Plan**: Ensure migration can be safely reversed if needed

### Security
- **Salt Storage**: Keep ANONYMITY_SALT secret and secure
- **Backup Strategy**: Ensure salt is included in backup/restore procedures

## Benefits of New System

### Simplified Architecture
- **No Mapping Table**: Eliminates most complex part of anonymity system
- **Direct Storage**: Hash stored directly on ballot for efficiency
- **Reduced Joins**: No additional database joins for anonymous vote display

### Enhanced Security
- **One-Way Protection**: Impossible to reverse hashes without salt
- **Reduced Attack Surface**: No separate table to secure
- **Salt-Based Security**: Even database compromise doesn't reveal usernames

### Improved Performance
- **Fewer Queries**: No joins to mapping table
- **Simpler Logic**: Straightforward display logic
- **Better Caching**: Easier to cache ballot data

### Easier Maintenance
- **No GUID Management**: No need to generate and track GUIDs
- **Simpler Deployment**: No special database encryption requirements
- **Clear Code Path**: Straightforward logic flow

## Future Considerations

### Salt Rotation
If salt rotation is ever needed:
1. Generate new salt
2. Rehash all existing usernames
3. Update environment variable
4. Deploy changes atomically

### Enhanced Verification
Future features could include:
- Batch verification of anonymous votes
- Statistical analysis without identity revelation
- Advanced privacy-preserving analytics

## Success Criteria

### Functional Requirements
- [ ] Anonymous votes display as "Anonymous" in all interfaces
- [ ] Public votes display actual usernames
- [ ] Hash verification works correctly
- [ ] User anonymity preferences are respected
- [ ] Migration completes successfully

### Security Requirements
- [ ] Hashes cannot be reversed without salt
- [ ] Salt is properly secured in environment variables
- [ ] No username information leaks in anonymous mode
- [ ] System maintains audit trail capabilities

### Performance Requirements
- [ ] No performance degradation in vote display
- [ ] Migration completes in reasonable time
- [ ] Hash generation is efficient for real-time voting

### Compatibility Requirements
- [ ] All existing functionality continues to work
- [ ] Delegation trees display correctly
- [ ] Results pages show proper anonymity
- [ ] Admin interface functions properly

This plan provides a comprehensive approach to simplifying CrowdVote's anonymity system while maintaining strong privacy protections and improving overall system maintainability.
