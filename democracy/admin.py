from django.contrib import admin

from .models import Community, Membership, Decision, Choice, Ballot, Vote, Result


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
    list_display = ['member', 'community', 'is_voting_community_member', 'is_community_manager', 'dt_joined']
    list_filter = ['is_voting_community_member', 'is_community_manager', 'is_anonymous_by_default', 'dt_joined']
    search_fields = ['member__username', 'community__name']
    raw_id_fields = ['member', 'community']


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
    """Admin interface for Ballot model."""
    list_display = ['voter', 'decision', 'is_calculated', 'is_anonymous', 'created']
    list_filter = ['is_calculated', 'is_anonymous', 'decision__community', 'created']
    search_fields = ['voter__username', 'decision__title']
    raw_id_fields = ['voter', 'decision']
    inlines = [VoteInline]
    
    # TODO: Re-enable when tagging is implemented
    # def tag_list(self, obj):
    #     """Display tags as a comma-separated list."""
    #     return ", ".join(o.name for o in obj.tags.all())
    # tag_list.short_description = 'Tags'


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
