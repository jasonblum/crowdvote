from django.contrib import admin
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.html import format_html


from .models import CustomUser, Following


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "first_name",
        "last_name",
        "email_link",
        "memberships",
        "followings",
    )
    search_fields = ("username", "email_link", "first_name", "last_name")

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related(
            "followings",
            "followings__followee",
            "memberships",
            "memberships__community",
        )

    def email_link(self, obj):
        return format_html(f"<a href=mailto:'{obj.email}'>{obj.email}</a>")

    def followings(self, obj):
        return format_html(
            ", ".join(
                [
                    f"<a href={reverse('admin:accounts_following_change', kwargs={'object_id': following.pk})}>{following} ({following.followee})</a>"
                    for following in obj.followings.all()
                ]
            )
        )

    def memberships(self, obj):
        return format_html(
            ", ".join(
                [
                    f"<a href={reverse('admin:communities_membership_change', kwargs={'object_id': membership.pk})}>{membership} ({membership.community})</a>"
                    for membership in obj.memberships.all()
                ]
            )
        )


@admin.register(Following)
class FollowingAdmin(admin.ModelAdmin):
    list_display = ("__str__", "user_link", "followee_link", "tags_list")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "user",
                "followee",
            )
            .prefetch_related("tags")
        ).distinct()

    def user_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:accounts_customuser_change', kwargs={'object_id': obj.user.pk})}>{obj.user}</a>"
        )

    user_link.short_description = "Follower"

    def followee_link(self, obj):
        return format_html(
            f"<a href={reverse('admin:accounts_customuser_change', kwargs={'object_id': obj.followee.pk})}>{obj.followee}</a>"
        )

    followee_link.short_description = "Followee"

    def tags_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())

    tags_list.short_description = "Tags"


admin.site.unregister(Group)
