from django.contrib import admin
from django_admin_listfilter_dropdown.filters import (
    DropdownFilter,
    RelatedDropdownFilter,
    ChoiceDropdownFilter,
)
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Membership,
    Community,
    Election,
    Ballot,
    Candidate,
    Vote,
)


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "name",
    )


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):

    list_display = (
        "__str__",
        "member_link",
        "community_link",
        "is_community_legislator",
        "is_community_manager",
        "is_voting_community_member",
        "dt_joined",
    )
    list_filter = (
        # for ordinary fields
        # ('a_charfield', DropdownFilter),
        # # for candidate fields
        ("community", ChoiceDropdownFilter),
        # for related fields
        # ('a_foreignkey_field', RelatedDropdownFilter),
        "is_community_legislator",
        "is_community_manager",
        "is_voting_community_member",
    )
    search_fields = ("member__username",)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("member", "community")

    def member_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:accounts_customuser_change', kwargs={'object_id': obj.member.pk})}>{obj.member.first_name} {obj.member.last_name}</a>"
        )

    member_link.short_description = "Voter"

    def community_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:communities_community_change', kwargs={'object_id': obj.community.pk})}>{obj.community}</a>"
        )

    community_link.short_description = "Community"


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):

    list_display = (
        "__str__",
        "dt_close",
        "community_link",
    )
    list_filter = (("community", ChoiceDropdownFilter),)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("community")

    def community_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:communities_community_change', kwargs={'object_id': obj.community.pk})}>{obj.community}</a>"
        )

    community_link.short_description = "Community"


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):

    list_display = (
        "__str__",
        "title",
        "election_link",
        "stars_html",
    )
    list_filter = (("election", ChoiceDropdownFilter),)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("election")

    def stars_html(self, obj):
        return "* " * obj.stars

    stars_html.short_description = "Stars"

    def election_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:communities_election_change', kwargs={'object_id': obj.election.pk})}>{obj.election}</a>"
        )

    election_link.short_description = "Election"


@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):

    list_display = ("__str__", "election_link", "voter_link", "tags_list")
    list_filter = (("election", ChoiceDropdownFilter),)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("election", "voter").prefetch_related("tags")

    def voter_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:accounts_customuser_change', kwargs={'object_id': obj.voter.pk})}>{obj.voter}</a>"
        )

    voter_link.short_description = "Voter"

    def election_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:communities_election_change', kwargs={'object_id': obj.election.pk})}>{obj.election}</a>"
        )

    election_link.short_description = "Election"

    def tags_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())

    tags_list.short_description = "Tags"


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):

    list_display = (
        "__str__",
        "candidate_link",
        "stars_html",
        "ballot_link",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("candidate", "ballot")

    def candidate_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:communities_candidate_change', kwargs={'object_id': obj.candidate.pk})}>{obj.candidate}</a>"
        )

    candidate_link.short_description = "Candidate"
    candidate_link.admin_order_field = "candidate_id"

    def ballot_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:communities_ballot_change', kwargs={'object_id': obj.ballot.pk})}>{obj.ballot}</a>"
        )

    ballot_link.short_description = "Ballot"
    ballot_link.admin_order_field = "ballot_id"

    def stars_html(self, obj):
        return "* " * obj.stars

    stars_html.short_description = "Stars"
    stars_html.admin_order_field = "stars"
