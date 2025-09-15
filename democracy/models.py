"""
Democracy models for the CrowdVote application.

This module contains all models related to democratic decision-making, including
communities, decisions, voting, and results. These models implement the core
functionality of CrowdVote's STAR voting system with delegative democracy.

Key concepts:
- Communities: Groups of users who make decisions together
- Decisions: Questions or proposals that communities vote on
- STAR Voting: Score Then Automatic Runoff voting system
- Delegative Democracy: Users can delegate votes or vote directly
- Ballot Inheritance: Votes can be calculated from delegation chains
"""

import uuid
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from taggit.managers import TaggableManager

from crowdvote.models import BaseModel

User = get_user_model()


class Community(BaseModel):
    """
    Represents a community of users who make decisions together.
    
    CrowdVote supports multiple communities, allowing users to participate in
    different groups (e.g., condo association, town council, student government).
    Each community operates independently with its own decisions and membership.
    
    Features:
    - Multi-community membership (users can belong to multiple communities)
    - Rich membership model with roles and permissions
    - Independent decision-making processes per community
    - Flexible membership management
    
    Attributes:
        name (CharField): Display name of the community
        description (TextField): Detailed description of the community's purpose
        members (ManyToManyField): Users who belong to this community (through Membership)
        auto_approve_applications (BooleanField): Auto-approve applications for demo mode
        member_count_display (BooleanField): Whether to show member count publicly
        application_message_required (BooleanField): Whether to require application messages
    """
    name = models.CharField(
        max_length=255,
        help_text="Display name of the community"
    )
    description = models.TextField(
        help_text="Detailed description of the community's purpose and scope"
    )
    members = models.ManyToManyField(
        User, 
        through="Membership",
        help_text="Users who belong to this community"
    )
    
    # Community management settings
    auto_approve_applications = models.BooleanField(
        default=False,
        help_text="Automatically approve membership applications (demo mode)"
    )
    
    member_count_display = models.BooleanField(
        default=True,
        help_text="Show member count publicly on community pages"
    )
    
    application_message_required = models.BooleanField(
        default=False,
        help_text="Require application message from users when applying"
    )

    class Meta:
        verbose_name_plural = "Communities"
        ordering = ["name"]

    def __str__(self):
        """Return string representation of the community."""
        return self.name
    
    @property
    def member_count(self):
        """Return the total number of members in this community."""
        return self.memberships.count()
    
    def get_stats(self):
        """Return comprehensive statistics about this community.
        
        Returns:
            dict: Dictionary containing member counts, decision counts, and other stats
        """
        return {
            'total_members': self.memberships.count(),
            'voting_members': self.memberships.filter(is_voting_community_member=True).count(),
            'managers': self.memberships.filter(is_community_manager=True).count(),
            'lobbyists': self.memberships.filter(is_voting_community_member=False).count(),
            'total_decisions': self.decisions.count(),
            'active_decisions': self.decisions.filter(dt_close__gt=timezone.now()).count(),
        }
    
    def get_voting_members(self):
        """
        Get all members who have voting rights in this community.
        
        Returns:
            QuerySet: Users who are voting members (not just lobbyists)
        """
        return self.members.filter(
            memberships__community=self,
            memberships__is_voting_community_member=True
        )
    
    def get_managers(self):
        """
        Get all members who can manage this community.
        
        Returns:
            QuerySet: Users who are community managers
        """
        return self.members.filter(
            memberships__community=self,
            memberships__is_community_manager=True
        )


class Membership(BaseModel):
    """
    Through-model for Community-User relationship with additional membership details.
    
    This model defines the relationship between users and communities, including
    their roles, permissions, and preferences within each community. It enables
    fine-grained control over who can vote, manage the community, and how their
    participation is handled.
    
    Membership Types:
    - Voting Members: Can cast ballots that count toward decision results
    - Lobbyists: Can vote and tag and be followed on their votes and tags, but their votes aren't counted.
    - Managers: Can manage community membership and settings
    
    Privacy Features:
    - Anonymous voting: Members can choose to hide their identity in votes
    - Flexible privacy controls per community
    
    Attributes:
        member (ForeignKey): The user who is a member of the community
        community (ForeignKey): The community the user belongs to
        is_anonymous_by_default (BooleanField): Whether member prefers anonymous voting
        is_community_manager (BooleanField): Whether member can manage the community
        is_voting_community_member (BooleanField): Whether member's votes count
        dt_joined (DateTimeField): When the member joined this community
    """
    member = models.ForeignKey(
        User, 
        related_name="memberships", 
        on_delete=models.PROTECT,
        help_text="The user who is a member of this community"
    )
    community = models.ForeignKey(
        Community, 
        related_name="memberships", 
        on_delete=models.PROTECT,
        help_text="The community this membership belongs to"
    )
    is_anonymous_by_default = models.BooleanField(
        default=True, 
        help_text="Whether this member prefers anonymous voting by default"
    )
    is_community_manager = models.BooleanField(
        default=False, 
        help_text="Whether this member can manage community membership and settings"
    )
    is_voting_community_member = models.BooleanField(
        default=False, 
        help_text="Whether this member's votes count (vs. being just a lobbyist)"
    )
    dt_joined = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        help_text="Timestamp when this member joined the community"
    )

    class Meta:
        ordering = ["community__name", "member__username"]
        verbose_name = "Community Membership"
        verbose_name_plural = "Community Memberships"
        # Ensure a user can only have one membership per community
        unique_together = ["member", "community"]

    def __str__(self):
        """Return string representation of the membership."""
        return f"{self.member.username} in {self.community.name}"
    
    @property
    def role_display(self):
        """
        Get a human-readable description of the member's role.
        
        Returns:
            str: Description of the member's role and permissions
        """
        roles = []
        if self.is_community_manager:
            roles.append("Manager")
        if self.is_voting_community_member:
            roles.append("Voter")
        else:
            roles.append("Lobbyist")
        
        return ", ".join(roles)


class Decision(BaseModel):
    """
    Represents a question or proposal that a community votes on.
    
    Decisions are the core of CrowdVote's democratic process. Each decision
    presents a question to the community with multiple choices that members
    can vote on using the STAR voting system (Score Then Automatic Runoff).
    
    Decision Lifecycle:
    1. Created by community members or managers
    2. Open for voting until dt_close
    3. Votes are tallied using STAR voting algorithm
    4. Results are calculated and stored
    5. Decision is closed and results are final
    
    Features:
    - Flexible voting periods with configurable close dates
    - Automatic result calculation triggers
    - Support for multiple choices per decision
    - Integration with delegative democracy system
    
    Attributes:
        title (CharField): Short, descriptive title of the decision
        description (TextField): Detailed description of what's being decided
        dt_close (DateTimeField): When voting closes and results are finalized
        community (ForeignKey): Which community this decision belongs to
        results_need_updating (BooleanField): Whether results need recalculation
    """
    title = models.CharField(
        max_length=255,
        help_text="Short, descriptive title of the decision"
    )
    description = models.TextField(
        help_text="Detailed description of what's being decided, including context and implications"
    )
    dt_close = models.DateTimeField(
        help_text="When voting closes and results are finalized (no more votes accepted)"
    )
    community = models.ForeignKey(
        Community, 
        related_name="decisions", 
        on_delete=models.PROTECT,
        help_text="The community this decision belongs to"
    )
    results_need_updating = models.BooleanField(
        default=True,
        help_text="Whether results need recalculation (set when new votes are cast)"
    )

    class Meta:
        ordering = ["-dt_close", "title"]

    def __str__(self):
        """Return string representation of the decision."""
        return self.title
    
    @property
    def choice_count(self):
        """Return the number of choices for this decision."""
        return self.choices.count()
    
    def get_participation_stats(self):
        """Return participation statistics for this decision.
        
        Returns:
            dict: Dictionary containing participation rates and vote counts
        """
        total_ballots = self.ballots.count()
        voting_member_ballots = self.ballots.filter(voter__memberships__community=self.community, 
                                                   voter__memberships__is_voting_community_member=True).count()
        total_voting_members = self.community.memberships.filter(is_voting_community_member=True).count()
        
        participation_rate = (voting_member_ballots / total_voting_members * 100) if total_voting_members > 0 else 0
        
        return {
            'total_ballots': total_ballots,
            'voting_member_ballots': voting_member_ballots,
            'total_voting_members': total_voting_members,
            'participation_rate': round(participation_rate, 1),
            'manual_ballots': self.ballots.filter(is_calculated=False).count(),
            'calculated_ballots': self.ballots.filter(is_calculated=True).count(),
        }

    def clean(self):
        """
        Validate the decision.
        
        Raises:
            ValidationError: If dt_close is in the past
        """
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        super().clean()
        
        if self.dt_close and self.dt_close <= timezone.now():
            raise ValidationError({
                'dt_close': 'Decision deadline cannot be in the past.'
            })

    @property
    def result(self):
        """
        Get the most recent result for this decision.
        
        Returns:
            Result or None: The latest calculated result, or None if no results exist
        """
        return self.results.first()
    
    @property
    def is_open(self):
        """
        Check if voting is still open for this decision.
        
        Returns:
            bool: True if voting is open, False if closed
        """
        return timezone.now() < self.dt_close
    
    
    def get_total_ballots(self):
        """
        Get the total number of ballots cast for this decision.
        
        Returns:
            int: Number of ballots (both manual and calculated)
        """
        return self.ballots.count()
    
    def get_voting_member_ballots(self):
        """
        Get ballots from members who have voting rights.
        
        Returns:
            QuerySet: Ballots from voting community members only
        """
        return self.ballots.filter(
            voter__memberships__community=self.community,
            voter__memberships__is_voting_community_member=True
        )
    
    def get_latest_snapshot(self):
        """
        Get the most recent snapshot for this decision.
        
        Returns:
            DecisionSnapshot or None: The latest snapshot for this decision
        """
        return self.snapshots.first()  # Uses related_name='snapshots' and ordering=['-created_at']
    
    def get_final_snapshot(self):
        """
        Get the final snapshot for this decision (if it exists).
        
        Returns:
            DecisionSnapshot or None: The final snapshot if decision is closed, None otherwise
        """
        return self.snapshots.filter(is_final=True).first()


class Choice(BaseModel):
    """
    Represents an individual option/choice within a Decision.
    
    Each Decision can have multiple choices that community members vote on
    using the STAR voting system. Choices are the specific options that
    voters can score from 0-5 stars.
    
    STAR Voting Process:
    1. Score Phase: Voters give each choice 0-5 stars
    2. Automatic Runoff: Top 2 choices compete based on voter preferences
    
    The score and runoff_score fields store the calculated results from
    the STAR voting algorithm.
    
    Attributes:
        title (CharField): Short name/title of this choice
        description (TextField): Detailed description of what this choice means
        decision (ForeignKey): The decision this choice belongs to
        score (DecimalField): Average star score from all votes (0.0000-5.0000)
        runoff_score (DecimalField): Score in automatic runoff phase
    """
    title = models.CharField(
        max_length=255,
        help_text="Short, descriptive name for this choice"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of what this choice represents"
    )
    decision = models.ForeignKey(
        Decision, 
        related_name="choices", 
        on_delete=models.PROTECT,
        help_text="The decision this choice belongs to"
    )
    
    # Score tracking fields (calculated by STAR voting algorithm)
    score = models.DecimalField(
        null=True,
        blank=True,
        default=0.0,
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
        help_text="Average star score from all votes (0.0000-5.0000)"
    )
    runoff_score = models.DecimalField(
        null=True,
        blank=True,
        default=0.0,
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
        help_text="Score in the automatic runoff phase of STAR voting"
    )

    class Meta:
        ordering = ["decision__title", "title"]

    def __str__(self):
        """Return string representation of the choice."""
        return self.title
    
    @property
    def vote_count(self):
        """Return the number of votes cast for this choice."""
        return self.votes.count()
    
    def get_average_score(self):
        """Calculate and return the average score for this choice.
        
        Returns:
            float: Average score from all votes, or 0.0 if no votes
        """
        votes = self.votes.all()
        if not votes:
            return 0.0
        
        total_stars = sum(vote.stars for vote in votes)
        return round(total_stars / len(votes), 2)

    def get_id_display(self):
        """Get a short display ID for this choice."""
        return f"Ch-{self.id}"
    
    def get_vote_count(self):
        """
        Get the total number of votes cast for this choice.
        
        Returns:
            int: Number of votes (from all ballots)
        """
        return self.votes.count()
    
    def get_average_stars(self):
        """
        Calculate the average star rating for this choice.
        
        Returns:
            float or None: Average stars (0.0-5.0) or None if no votes
        """
        from django.db.models import Avg
        result = self.votes.aggregate(avg_stars=Avg('stars'))
        return result['avg_stars']


class Ballot(BaseModel):
    """
    Represents a user's complete vote on a Decision.
    
    A ballot contains all of a user's votes (star ratings) for the choices
    in a decision. Ballots can be either:
    1. Manually cast: User directly votes on each choice
    2. Calculated: System calculates votes based on delegation chains
    
    Delegation System:
    - If a user doesn't vote directly, the system can calculate their ballot
    - Calculation follows the user's Following relationships
    - Multiple levels of delegation are supported (A follows B, B follows C)
    - Users can always override calculated ballots by voting directly
    
    Privacy Features:
    - Anonymous voting: When is_anonymous=True, user's identity is hidden in reports
    - GUID mapping: Anonymous voters appear as GUIDs in public reports
    - Per-decision anonymity: Users can override their default anonymity preference
    - Comments: Users can explain their reasoning (optional)
    
    Attributes:
        id (UUIDField): Unique identifier for this ballot
        decision (ForeignKey): The decision this ballot is for
        voter (ForeignKey): The user who cast (or will have calculated) this ballot
        is_calculated (BooleanField): Whether this ballot was calculated vs. manual
        is_anonymous (BooleanField): Whether this ballot should be anonymous
        comments (TextField): Optional explanation of voting reasoning
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique identifier for this ballot"
    )
    decision = models.ForeignKey(
        Decision, 
        related_name="ballots", 
        on_delete=models.PROTECT,
        help_text="The decision this ballot is voting on"
    )
    voter = models.ForeignKey(
        User, 
        related_name="ballots", 
        on_delete=models.PROTECT,
        help_text="The user who cast this ballot (or had it calculated)"
    )
    is_calculated = models.BooleanField(
        default=False,
        help_text="True if calculated by delegation system, False if manually cast"
    )
    is_anonymous = models.BooleanField(
        default=True,
        help_text="Whether this ballot should be kept anonymous"
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Comma-separated tags this voter applied to characterize this decision (e.g., 'environmental,fiscal')"
    )
    comments = models.TextField(
        blank=True,
        help_text="Optional explanation of voting reasoning or context"
    )

    class Meta:
        ordering = ["decision__title", "voter__username"]
        # Ensure one ballot per user per decision
        unique_together = ["decision", "voter"]

    def __str__(self):
        """Return string representation of the ballot."""
        return f"{self.voter.username}'s ballot on {self.decision.title}"

    def get_preferred_choice(self):
        """
        Determine the voter's preferred choice for STAR voting runoff.
        
        In STAR voting, after the scoring phase, the top 2 choices go to
        an automatic runoff where each voter's preference determines the winner.
        
        Returns:
            Choice or None: The choice this voter prefers, or None if tied/no preference
            
        References:
            https://www.starvoting.us/ties - STAR voting tie-breaking rules
        """
        # TODO: Implement STAR voting preferred choice logic
        # This should:
        # 1. Get the voter's star ratings for all choices
        # 2. Determine which choice they gave the highest rating to
        # 3. Handle ties according to STAR voting rules
        pass
    
    def get_total_stars_cast(self):
        """
        Get the total number of stars this voter cast across all choices.
        
        Returns:
            int: Sum of all star ratings in this ballot
        """
        from django.db.models import Sum
        result = self.votes.aggregate(total_stars=Sum('stars'))
        return result['total_stars'] or 0
    
    def is_complete(self):
        """
        Check if this ballot has votes for all choices in the decision.
        
        Returns:
            bool: True if voter has rated all choices, False otherwise
        """
        choice_count = self.decision.choices.count()
        vote_count = self.votes.count()
        return choice_count == vote_count

    def get_display_name(self):
        """
        Get the display name for this ballot's voter (real name or anonymous GUID).
        
        This method determines whether to show the voter's real username or an
        anonymous GUID based on their anonymity preference for this decision.
        
        Returns:
            str: Either the real username or an anonymous GUID
        """
        return AnonymousVoteMapping.get_display_name(self.decision, self.voter)

    def set_anonymity_preference(self, is_anonymous=None):
        """
        Set the anonymity preference for this ballot.
        
        If no preference is provided, uses the user's default anonymity setting
        from their membership in this decision's community.
        
        Args:
            is_anonymous (bool, optional): Override anonymity preference.
                If None, uses user's default setting.
        """
        if is_anonymous is not None:
            self.is_anonymous = is_anonymous
        else:
            # Use user's default anonymity preference from their community membership
            try:
                membership = self.voter.memberships.get(community=self.decision.community)
                self.is_anonymous = membership.is_anonymous_by_default
            except:
                # Fallback to anonymous if membership not found
                self.is_anonymous = True


class Vote(BaseModel):
    """
    Represents an individual star rating for a specific Choice within a Ballot.
    
    In STAR voting, voters rate each choice from 0-5 stars. Each Vote record
    represents one voter's rating for one choice. A complete Ballot contains
    multiple Vote records (one for each Choice in the Decision).
    
    STAR Voting Scale:
    - 0 stars: Strongly oppose or worst option
    - 1 star: Oppose or poor option  
    - 2 stars: Neutral or acceptable option
    - 3 stars: Support or good option
    - 4 stars: Strongly support or very good option
    - 5 stars: Enthusiastic support or best option
    
    Attributes:
        id (UUIDField): Unique identifier for this vote
        choice (ForeignKey): The choice being rated
        stars (PositiveSmallIntegerField): Star rating from 0-5
        ballot (ForeignKey): The ballot this vote belongs to
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique identifier for this vote"
    )
    choice = models.ForeignKey(
        Choice, 
        related_name="votes", 
        on_delete=models.PROTECT,
        help_text="The choice being rated in this vote"
    )
    stars = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Star rating from 0.00 (worst) to 5.00 (best) for this choice - supports fractional ratings from delegation averaging"
    )
    ballot = models.ForeignKey(
        Ballot,
        related_name="votes",
        on_delete=models.PROTECT,
        help_text="The ballot this vote belongs to"
    )

    class Meta:
        ordering = ["choice"]
        # Ensure one vote per choice per ballot
        unique_together = ["choice", "ballot"]

    def __str__(self):
        """Return string representation of the vote."""
        return f"{self.stars} stars for {self.choice.title}"
    
    def clean(self):
        """
        Validate the vote.
        
        Raises:
            ValidationError: If choice doesn't belong to ballot's decision
        """
        from django.core.exceptions import ValidationError
        
        if self.choice.decision != self.ballot.decision:
            raise ValidationError(
                "Vote choice must belong to the same decision as the ballot."
            )
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.clean()
        super().save(*args, **kwargs)


class Result(BaseModel):
    """
    Stores the calculated results and statistics for a Decision.
    
    After voting closes (or when results need updating), the STAR voting
    algorithm calculates the results and stores them in this model. This
    provides both human-readable reports and detailed statistics for
    transparency and auditability.
    
    STAR Voting Results Include:
    - Score phase: Average star ratings for each choice
    - Runoff phase: Head-to-head comparison of top 2 choices
    - Winner determination and margin of victory
    - Detailed vote breakdowns and statistics
    - Ballot inheritance tree (showing delegation chains)
    
    Features:
    - Multiple result snapshots (results are recalculated when votes change)
    - Comprehensive audit trail with detailed statistics
    - Human-readable reports for community members
    - Machine-readable data for API access and analysis
    
    Attributes:
        decision (ForeignKey): The decision these results are for
        report (TextField): Human-readable summary of results
        stats (JSONField): Detailed statistics and calculation data
    """
    decision = models.ForeignKey(
        Decision, 
        related_name="results", 
        on_delete=models.PROTECT,
        help_text="The decision these results are for"
    )
    report = models.TextField(
        help_text="Human-readable summary of the voting results and winner"
    )
    stats = models.JSONField(
        help_text="Detailed statistics including vote counts, averages, delegation chains, and audit data"
    )

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        """Return string representation of the result."""
        return f"Results for {self.decision.title}"
    
    def get_winner(self):
        """
        Extract the winning choice from the results.
        
        Returns:
            dict or None: Winner information from stats, or None if no winner
        """
        if 'winner' in self.stats:
            return self.stats['winner']
        return None
    
    def get_score_phase_results(self):
        """
        Get the score phase results (average star ratings).
        
        Returns:
            list: Choices ordered by average star rating
        """
        if 'score_phase' in self.stats:
            return self.stats['score_phase']
        return []
    
    def get_runoff_results(self):
        """
        Get the automatic runoff results (top 2 choices head-to-head).
        
        Returns:
            list: Runoff results, or empty list if no runoff occurred
        """
        if 'runoff_phase' in self.stats:
            return self.stats['runoff_phase']
        return []
    
    def get_participation_stats(self):
        """
        Get participation statistics (total ballots, delegation info, etc.).
        
        Returns:
            dict: Participation and delegation statistics
        """
        if 'participation' in self.stats:
            return self.stats['participation']
        return {}


class AnonymousVoteMapping(BaseModel):
    """
    Secure mapping between anonymous GUIDs and actual users for specific decisions.
    
    CORE CONCEPT: Solves the tension between transparency and privacy through count verification.
    - Community page shows "100 real usernames" (establishes total legitimate membership)  
    - Decision page shows "100 mixed names + GUIDs" (same count = trust maintained)
    - Anonymous users get different GUIDs per decision for privacy
    - Follow paths work seamlessly: "Alice → Bob → 9d01fbb1-3fa7-499b-81b0-706d4d11ffb0"
    
    This model enables anonymous voting while maintaining verifiable community membership.
    When a user chooses to vote anonymously on a decision, a GUID is generated and 
    displayed in public reports instead of their username. This table maintains the 
    secure mapping between the GUID and the actual user.
    
    Key Security Features:
    - One GUID per user per decision (users get different GUIDs for different decisions)
    - Only the system can access this mapping (not even superusers in production)
    - Enables verification that anonymous voters are legitimate community members
    - Supports the "100 real names vs. 100 mixed names+GUIDs" verification system
    
    Privacy Architecture:
    - Community page: Shows 100 real usernames (establishes total membership)
    - Decision page: Shows mix of real names + GUIDs (same count = trust)
    - Follow paths: Work with both real names and GUIDs (e.g., "Alice → Bob → 9d01fbb1...")
    - Audit trails: Complete transparency while preserving individual privacy
    
    Attributes:
        decision (ForeignKey): The specific decision this anonymity applies to
        user (ForeignKey): The actual user who is voting anonymously
        anonymous_guid (UUIDField): The GUID displayed in public reports
        created_at (DateTimeField): When this anonymous mapping was created
    """
    
    decision = models.ForeignKey(
        Decision,
        on_delete=models.CASCADE,
        related_name='anonymous_mappings',
        help_text="The decision this anonymous mapping applies to"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='anonymous_mappings',
        help_text="The actual user who is voting anonymously"
    )
    
    anonymous_guid = models.UUIDField(
        default=uuid.uuid4,
        help_text="The GUID displayed in public reports instead of the username"
    )

    class Meta:
        ordering = ['-created']
        verbose_name = "Anonymous Vote Mapping"
        verbose_name_plural = "Anonymous Vote Mappings"
        # Ensure one anonymous GUID per user per decision
        unique_together = ['decision', 'user']
        # In production, this table should be heavily secured/encrypted
        db_table = 'democracy_anonymous_vote_mapping'

    def __str__(self):
        """Return string representation of the mapping."""
        return f"Anonymous mapping for {self.user.username} on {self.decision.title}"

    @classmethod
    def get_or_create_guid(cls, decision, user):
        """
        Get existing GUID or create new one for user on this decision.
        
        Args:
            decision (Decision): The decision being voted on
            user (CustomUser): The user voting anonymously
            
        Returns:
            str: The anonymous GUID for this user on this decision
        """
        mapping, created = cls.objects.get_or_create(
            decision=decision,
            user=user
        )
        return str(mapping.anonymous_guid)

    @classmethod
    def get_display_name(cls, decision, user):
        """
        Get the display name for a user on a specific decision.
        
        This is the core method that determines whether to show the real username
        or an anonymous GUID based on the user's anonymity preference and ballot settings.
        
        Args:
            decision (Decision): The decision being reported on
            user (CustomUser): The user whose name to display
            
        Returns:
            str: Either the real username or an anonymous GUID
        """
        try:
            # Check if user has a ballot for this decision
            ballot = decision.ballots.get(voter=user)
            
            if ballot.is_anonymous:
                # User chose to be anonymous - return user-friendly anonymous name
                guid = cls.get_or_create_guid(decision, user)
                return f"Anonymous Voter #{guid[:8]}"
            else:
                # User chose to be public - return real username
                return user.username
                
        except Ballot.DoesNotExist:
            # No ballot exists - return real username (for community member lists)
            return user.username

    def get_real_user(self):
        """
        Get the real user behind this anonymous GUID.
        
        WARNING: This method should only be used by system processes,
        never exposed to end users or even administrators.
        
        Returns:
            CustomUser: The actual user behind the anonymous GUID
        """
        return self.user


class DecisionSnapshot(BaseModel):
    """
    Represents a point-in-time snapshot of a decision's complete state and results.
    
    This model stores pre-calculated results to ensure consistency and performance.
    When votes, tags, or following relationships change, a new snapshot is created
    with updated calculations. This prevents inconsistencies during long-running
    calculations and provides historical audit trails.
    
    Key Features:
    - Point-in-time data consistency (immutable once created)
    - Complete system state capture at calculation time
    - Performance optimization through pre-calculation
    - Historical audit trail of result changes
    - Support for final vs intermediate snapshots
    
    Attributes:
        decision (ForeignKey): The decision this snapshot represents
        created_at (DateTimeField): When this snapshot was calculated
        snapshot_data (JSONField): Complete system state and calculation results
        calculation_duration (DurationField): How long the calculation took
        total_eligible_voters (IntegerField): Number of voting community members
        total_votes_cast (IntegerField): Number of direct votes submitted
        total_calculated_votes (IntegerField): Number of votes calculated via delegation
        tags_used (JSONField): All tags used in voting with frequency counts
        is_final (BooleanField): True when decision is closed (final results)
        
    JSON Structure for snapshot_data:
    {
        "metadata": {
            "calculation_timestamp": "2025-01-07T15:30:00Z",
            "system_version": "1.0.0",
            "decision_status": "active|closed|draft"
        },
        "delegation_tree": {
            "nodes": [...],  # All voters and their relationships
            "edges": [...],  # Following relationships with tags
            "inheritance_chains": [...]  # Vote inheritance paths
        },
        "vote_tally": {
            "direct_votes": [...],  # Manually cast votes
            "calculated_votes": [...],  # Inherited votes
            "anonymized_mapping": {...}  # GUID to vote mapping
        },
        "star_results": {
            "score_phase": {...},  # Average scores per choice
            "runoff_phase": {...},  # Top 2 choices runoff
            "winner": "choice_id",
            "margin": 0.15,
            "statistics": {...}  # Additional metrics
        },
        "tag_analysis": {
            "tag_frequency": {...},  # How often each tag was used
            "delegation_by_tag": {...},  # Delegation patterns per tag
            "influence_scores": {...}  # Member influence by tag
        }
    }
    """
    
    decision = models.ForeignKey(
        Decision,
        on_delete=models.CASCADE,
        related_name='snapshots',
        help_text="The decision this snapshot represents"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this snapshot was calculated"
    )
    
    snapshot_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Complete system state and calculation results at snapshot time"
    )
    
    calculation_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="How long the calculation took to complete"
    )
    
    total_eligible_voters = models.IntegerField(
        default=0,
        help_text="Number of voting community members at snapshot time"
    )
    
    total_votes_cast = models.IntegerField(
        default=0,
        help_text="Number of direct votes submitted by users"
    )
    
    total_calculated_votes = models.IntegerField(
        default=0,
        help_text="Number of votes calculated via delegation chains"
    )
    
    tags_used = models.JSONField(
        default=list,
        blank=True,
        help_text="All tags used in voting with frequency counts"
    )
    
    is_final = models.BooleanField(
        default=False,
        help_text="True when decision is closed and results are final"
    )
    
    # Error handling and status tracking fields
    calculation_status = models.CharField(
        max_length=20,
        choices=[
            ('creating', 'Creating Snapshot'),
            ('ready', 'Ready for Calculation'),
            ('staging', 'Stage Ballots in Progress'),
            ('tallying', 'Tally in Progress'),
            ('completed', 'Calculation Completed'),
            ('failed_snapshot', 'Snapshot Creation Failed'),
            ('failed_staging', 'Stage Ballots Failed'),
            ('failed_tallying', 'Tally Failed'),
            ('corrupted', 'Snapshot Corrupted')
        ],
        default='ready',
        help_text="Current status of the calculation process"
    )
    
    error_log = models.TextField(
        blank=True,
        help_text="Detailed error information if calculation failed"
    )
    
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of retry attempts for failed calculations"
    )
    
    last_error = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last error occurred during calculation"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Decision Snapshot"
        verbose_name_plural = "Decision Snapshots"
        indexes = [
            models.Index(fields=['decision', '-created_at']),
            models.Index(fields=['decision', 'is_final']),
        ]
    
    def __str__(self):
        status = "Final" if self.is_final else "Interim"
        return f"{status} snapshot for '{self.decision.title}' ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    
    def clean(self):
        """
        Validate that only one final snapshot exists per decision.
        """
        from django.core.exceptions import ValidationError
        
        if self.is_final:
            existing_final = DecisionSnapshot.objects.filter(
                decision=self.decision,
                is_final=True
            ).exclude(pk=self.pk)
            
            if existing_final.exists():
                raise ValidationError({
                    'is_final': 'Only one final snapshot is allowed per decision.'
                })
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation runs and handle final snapshot logic.
        """
        from django.core.exceptions import ValidationError
        
        self.full_clean()
        
        # If this is being marked as final, ensure decision is actually closed
        if self.is_final and self.decision.is_open:
            raise ValidationError("Cannot create final snapshot for open decision")
            
        super().save(*args, **kwargs)
    
    @property
    def participation_rate(self):
        """Calculate the participation rate as a percentage."""
        if self.total_eligible_voters == 0:
            return 0.0
        total_participants = self.total_votes_cast + self.total_calculated_votes
        return (total_participants / self.total_eligible_voters) * 100
    
    @property
    def delegation_rate(self):
        """Calculate what percentage of votes were calculated via delegation."""
        total_votes = self.total_votes_cast + self.total_calculated_votes
        if total_votes == 0:
            return 0.0
        return (self.total_calculated_votes / total_votes) * 100
    


