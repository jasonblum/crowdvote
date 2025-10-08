from django.contrib import admin

from .models import Community, Membership, Following, Decision, Choice, Ballot, Vote, Result, DecisionSnapshot


class MembershipInline(admin.TabularInline):
    """Inline for managing memberships within Community admin."""
    model = Membership
    extra = 0
    raw_id_fields = ['member']


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    """Admin interface for Community model."""
    list_display = ['name', 'member_count', 'created']
    list_filter = ['created', 'modified']
    search_fields = ['name', 'description']
    inlines = [MembershipInline]
    
    def member_count(self, obj):
        """Display number of members."""
        return obj.members.count()
    member_count.short_description = 'Members'


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    """Admin interface for Membership model."""
    list_display = ['member', 'community', 'is_voting_community_member', 'is_community_manager', 'is_anonymous', 'dt_joined']
    list_filter = ['is_voting_community_member', 'is_community_manager', 'is_anonymous', 'dt_joined']
    search_fields = ['member__username', 'community__name']
    raw_id_fields = ['member', 'community']


@admin.register(Following)
class FollowingAdmin(admin.ModelAdmin):
    """Admin interface for Following model."""
    list_display = ['follower_display', 'followee_display', 'community_display', 'tags_display', 'order', 'created']
    list_filter = ['follower__community', 'order', 'created']
    search_fields = [
        'follower__member__username',
        'followee__member__username',
        'follower__community__name',
        'tags'
    ]
    raw_id_fields = ['follower', 'followee']
    ordering = ['follower__community', 'follower__member__username', 'order']
    
    def follower_display(self, obj):
        """Display follower with username."""
        return f"{obj.follower.member.username}"
    follower_display.short_description = 'Follower'
    
    def followee_display(self, obj):
        """Display followee with username."""
        return f"{obj.followee.member.username}"
    followee_display.short_description = 'Followee'
    
    def community_display(self, obj):
        """Display community name."""
        return obj.follower.community.name
    community_display.short_description = 'Community'
    
    def tags_display(self, obj):
        """Display tags or indicate all tags."""
        return obj.tags if obj.tags else "(all tags)"
    tags_display.short_description = 'Tags'


class ChoiceInline(admin.TabularInline):
    """Inline for managing choices within Decision admin."""
    model = Choice
    extra = 0


@admin.register(Decision)
class DecisionAdmin(admin.ModelAdmin):
    """Admin interface for Decision model."""
    list_display = ['title', 'community', 'dt_close', 'results_need_updating', 'created']
    list_filter = ['community', 'results_need_updating', 'dt_close', 'created']
    search_fields = ['title', 'description', 'community__name']
    raw_id_fields = ['community']
    inlines = [ChoiceInline]
    date_hierarchy = 'dt_close'


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    """Admin interface for Choice model."""
    list_display = ['title', 'decision', 'score', 'runoff_score']
    list_filter = ['decision__community', 'created']
    search_fields = ['title', 'description', 'decision__title']
    raw_id_fields = ['decision']


class VoteInline(admin.TabularInline):
    """Inline for managing votes within Ballot admin."""
    model = Vote
    extra = 0
    raw_id_fields = ['choice']


@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):
    """
    Admin interface for Ballot model.
    
    Note: Anonymity is now controlled at the Membership level, not per-ballot.
    To check if a voter is anonymous, look at their membership in the decision's community.
    """
    list_display = ['voter', 'decision', 'tags_display', 'is_calculated', 'created']
    list_filter = ['is_calculated', 'decision__community', 'created']
    search_fields = ['voter__username', 'decision__title', 'tags']
    raw_id_fields = ['voter', 'decision']
    inlines = [VoteInline]
    
    def tags_display(self, obj):
        """Display tags as a comma-separated list."""
        return obj.tags if obj.tags else "(no tags)"
    tags_display.short_description = 'Tags'


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    """Admin interface for Vote model."""
    list_display = ['ballot', 'choice', 'stars', 'created']
    list_filter = ['stars', 'choice__decision__community', 'created']
    search_fields = ['ballot__voter__username', 'choice__title']
    raw_id_fields = ['ballot', 'choice']


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    """Admin interface for Result model."""
    list_display = ['decision', 'created']
    list_filter = ['decision__community', 'created']
    search_fields = ['decision__title']
    raw_id_fields = ['decision']
    readonly_fields = ['stats']


@admin.register(DecisionSnapshot)
class DecisionSnapshotAdmin(admin.ModelAdmin):
    """Admin interface for DecisionSnapshot model."""
    list_display = [
        'decision', 
        'created_at', 
        'is_final', 
        'total_eligible_voters', 
        'total_votes_cast', 
        'total_calculated_votes',
        'participation_rate_display',
        'calculation_duration'
    ]
    list_filter = [
        'is_final', 
        'decision__community',
        'decision',
        'created_at',
        'decision__dt_close'
    ]
    search_fields = ['decision__title', 'decision__community__name']
    raw_id_fields = ['decision']
    readonly_fields = [
        'created_at',
        'participation_rate_display',
        'delegation_rate_display',
        'snapshot_data_preview'
    ]
    date_hierarchy = 'created_at'
    
    def participation_rate_display(self, obj):
        """Display participation rate as a formatted percentage."""
        return f"{obj.participation_rate:.1f}%"
    participation_rate_display.short_description = 'Participation Rate'
    
    def delegation_rate_display(self, obj):
        """Display delegation rate as a formatted percentage."""
        return f"{obj.delegation_rate:.1f}%"
    delegation_rate_display.short_description = 'Delegation Rate'
    
    def snapshot_data_preview(self, obj):
        """Display a preview of the snapshot data structure."""
        if not obj.snapshot_data:
            return "(No data)"
        
        preview_keys = []
        for key in ['metadata', 'delegation_tree', 'vote_tally', 'star_results', 'tag_analysis']:
            if key in obj.snapshot_data:
                preview_keys.append(key)
        
        if preview_keys:
            return f"Contains: {', '.join(preview_keys)}"
        else:
            return f"Keys: {', '.join(obj.snapshot_data.keys())}"
    snapshot_data_preview.short_description = 'Snapshot Data Preview'
