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
    Referendum,
    Ballot,
    Choice,
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
        "is_community_manager",
        "is_voting_community_member",
        "dt_joined",
    )
    list_filter = (
        # for ordinary fields
        # ('a_charfield', DropdownFilter),
        # # for choice fields
        ("community", ChoiceDropdownFilter),
        # for related fields
        # ('a_foreignkey_field', RelatedDropdownFilter),
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


@admin.register(Referendum)
class ReferendumnAdmin(admin.ModelAdmin):

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


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):

    list_display = (
        "__str__",
        "title",
        "referendum_link",
        "stars_html",
    )
    list_filter = (("referendum", ChoiceDropdownFilter),)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("referendum")

    def stars_html(self, obj):
        return "* " * obj.stars

    stars_html.short_description = "Stars"

    def referendum_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:communities_referendum_change', kwargs={'object_id': obj.referendum.pk})}>{obj.referendum}</a>"
        )

    referendum_link.short_description = "Referendum"


@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):

    list_display = ("__str__", "referendum_link", "voter_link", "tags_list")
    list_filter = (("referendum", ChoiceDropdownFilter),)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("referendum", "membership").prefetch_related(
            "tags"
        )

    def voter_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:accounts_customuser_change', kwargs={'object_id': obj.membership.member.pk})}>{obj.voter}</a>"
        )

    voter_link.short_description = "Voter"

    def referendum_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:communities_referendum_change', kwargs={'object_id': obj.referendum.pk})}>{obj.referendum}</a>"
        )

    referendum_link.short_description = "Referendum"

    def tags_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())

    tags_list.short_description = "Tags"


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):

    list_display = (
        "__str__",
        "choice_link",
        "stars_html",
        "ballot_link",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("choice", "ballot")

    def choice_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:communities_choice_change', kwargs={'object_id': obj.choice.pk})}>{obj.choice}</a>"
        )

    choice_link.short_description = "Choice"
    choice_link.admin_order_field = "choice_id"

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
