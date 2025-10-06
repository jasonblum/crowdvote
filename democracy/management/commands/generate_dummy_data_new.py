import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from security.models import Following
from democracy.models import Community, Membership, Decision, Choice, Ballot, Vote

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate realistic dummy data with multi-level delegation chains'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-data',
            action='store_true',
            help='Clear existing data before generating new data'
        )

    def handle(self, *args, **options):
        if options['clear_data']:
            self.clear_existing_data()
        
        self.stdout.write(
            self.style.SUCCESS('Generating REALISTIC community with proper voting patterns...')
        )

        # Create communities
        communities = self.create_communities()
        
        # Create users with specific voting patterns
        all_users = []
        for community in communities:
            users = self.create_users_for_community(community)
            all_users.extend(users)
        
        # Add specific test users for delegation debugging
        test_users = self.create_test_delegation_users(communities)
        all_users.extend(test_users)
        
        # Create test decisions FIRST
        decisions = self.create_test_decisions(communities)
        
        # Create manual votes (seed votes for delegation) - CRITICAL STEP
        self.create_realistic_manual_votes(decisions, all_users)
        
        # Create realistic multi-level delegation chains
        self.create_multilevel_delegation_chains(all_users)
        
        # Create specific test delegation pattern with circular reference prevention
        self.create_test_delegation_relationships(all_users)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully generated realistic delegation data!\n'
                f'- 2 communities with 30+ users each\n'
                f'- 10 manual voters per community\n'
                f'- 15+ calculated voters with multi-level chains\n'
                f'- 5 non-voters per community\n'
                f'- 8 test users (A-H) with specific delegation patterns\n'
                f'- Deep delegation trees up to 4+ levels\n'
                f'- Diverse tags: governance, budget, environment, safety, etc.\n'
            )
        )

    def clear_existing_data(self):
        """Clear existing data."""
        self.stdout.write('Clearing existing data...')
        Vote.objects.all().delete()
        Ballot.objects.all().delete()
        Choice.objects.all().delete()  # Clear choices first
        Decision.objects.all().delete()
        Following.objects.all().delete()
        Membership.objects.all().delete()
        # Don't delete communities and users - just relationships

    def create_communities(self):
        """Create Minion Collective and Springfield communities."""
        minion_community, _ = Community.objects.get_or_create(
            name='Minion Collective',
            defaults={
                'description': 'A community of lovable yellow creatures planning world domination and banana-related activities.',
                'auto_approve_applications': True
            }
        )
        
        springfield_community, _ = Community.objects.get_or_create(
            name='Springfield Town Council',
            defaults={
                'description': 'The quirky residents of Springfield making important municipal decisions (when not at Moe\'s Tavern).',
                'auto_approve_applications': True
            }
        )
        
        return [minion_community, springfield_community]

    def create_users_for_community(self, community):
        """Create exactly 30 users per community with specific roles."""
        if community.name == 'Minion Collective':
            return self.create_minion_users()
        else:
            return self.create_springfield_users()

    def create_minion_users(self):
        """Create 30 Minion-themed users."""
        # 10 manual voters (leaders)
        manual_voters = [
            ('kevin_minion', 'Kevin', 'Minion'),
            ('stuart_minion', 'Stuart', 'Minion'), 
            ('bob_minion', 'Bob', 'Minion'),
            ('gru_leader', 'Gru', 'Leader'),
            ('jerry_minion', 'Jerry', 'Minion'),
            ('dave_minion', 'Dave', 'Minion'),
            ('phil_minion', 'Phil', 'Minion'),
            ('tim_minion', 'Tim', 'Minion'),
            ('mark_minion', 'Mark', 'Minion'),
            ('steve_minion', 'Steve', 'Minion'),
        ]
        
        # 15 calculated voters (followers)
        calculated_voters = [
            ('banana_lover_1', 'Banana', 'Lover'),
            ('yellow_fellow_2', 'Yellow', 'Fellow'),
            ('goggle_guy_3', 'Goggle', 'Guy'),
            ('overall_dude_4', 'Overall', 'Dude'),
            ('short_stack_5', 'Short', 'Stack'),
            ('tall_minion_6', 'Tall', 'Minion'),
            ('one_eye_7', 'One', 'Eye'),
            ('two_eye_8', 'Two', 'Eye'),
            ('bello_banana_9', 'Bello', 'Banana'),
            ('papoy_minion_10', 'Papoy', 'Minion'),
            ('tulaliloo_11', 'Tulaliloo', 'Minion'),
            ('poopaye_12', 'Poopaye', 'Minion'),
            ('tank_yu_13', 'Tank', 'Yu'),
            ('me_want_banana_14', 'MeWant', 'Banana'),
            ('baboi_minion_15', 'Baboi', 'Minion'),
        ]
        
        # 5 non-voters (inactive)
        non_voters = [
            ('lazy_minion_1', 'Lazy', 'Minion'),
            ('sleepy_minion_2', 'Sleepy', 'Minion'),
            ('absent_minion_3', 'Absent', 'Minion'),
            ('busy_minion_4', 'Busy', 'Minion'),
            ('distracted_minion_5', 'Distracted', 'Minion'),
        ]
        
        all_minion_data = manual_voters + calculated_voters + non_voters
        users = []
        
        for username, first_name, last_name in all_minion_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f'{username}@minions.com',
                    'is_active': True,
                }
            )
            users.append(user)
            
            # Create membership
            community = Community.objects.get(name='Minion Collective')
            Membership.objects.get_or_create(
                member=user,
                community=community,
                defaults={
                    'is_voting_community_member': username not in [u[0] for u in non_voters],
                    'is_community_manager': username == 'gru_leader'
                }
            )
        
        return users

    def create_springfield_users(self):
        """Create 30 Springfield-themed users."""
        # 10 manual voters (leaders)
        manual_voters = [
            ('homer_simpson', 'Homer', 'Simpson'),
            ('marge_simpson', 'Marge', 'Simpson'),
            ('lisa_simpson', 'Lisa', 'Simpson'),
            ('ned_flanders', 'Ned', 'Flanders'),
            ('chief_wiggum', 'Chief', 'Wiggum'),
            ('apu_nahasapeemapetilon', 'Apu', 'Nahasapeemapetilon'),
            ('moe_szyslak', 'Moe', 'Szyslak'),
            ('mayor_quimby', 'Mayor', 'Quimby'),
            ('kent_brockman', 'Kent', 'Brockman'),
            ('reverend_lovejoy', 'Reverend', 'Lovejoy'),
        ]
        
        # 15 calculated voters (followers)
        calculated_voters = [
            ('bart_simpson', 'Bart', 'Simpson'),
            ('milhouse_van_houten', 'Milhouse', 'VanHouten'),
            ('nelson_muntz', 'Nelson', 'Muntz'),
            ('ralph_wiggum', 'Ralph', 'Wiggum'),
            ('martin_prince', 'Martin', 'Prince'),
            ('barney_gumble', 'Barney', 'Gumble'),
            ('carl_carlson', 'Carl', 'Carlson'),
            ('lenny_leonard', 'Lenny', 'Leonard'),
            ('selma_bouvier', 'Selma', 'Bouvier'),
            ('patty_bouvier', 'Patty', 'Bouvier'),
            ('groundskeeper_willie', 'Willie', 'MacDougal'),
            ('comic_book_guy', 'Comic', 'BookGuy'),
            ('professor_frink', 'Professor', 'Frink'),
            ('dr_hibbert', 'Dr', 'Hibbert'),
            ('snake_jailbird', 'Snake', 'Jailbird'),
        ]
        
        # 5 non-voters (inactive)
        non_voters = [
            ('maggie_simpson', 'Maggie', 'Simpson'),  # too young
            ('santa_little_helper', 'Santa', 'LittleHelper'),  # dog
            ('snowball_cat', 'Snowball', 'Cat'),  # cat
            ('duffman', 'Duff', 'Man'),  # always partying
            ('itchy_scratchy', 'Itchy', 'Scratchy'),  # fictional
        ]
        
        all_springfield_data = manual_voters + calculated_voters + non_voters
        users = []
        
        for username, first_name, last_name in all_springfield_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f'{username}@springfield.gov',
                    'is_active': True,
                }
            )
            users.append(user)
            
            # Create membership
            community = Community.objects.get(name='Springfield Town Council')
            Membership.objects.get_or_create(
                member=user,
                community=community,
                defaults={
                    'is_voting_community_member': username not in [u[0] for u in non_voters],
                    'is_community_manager': username == 'mayor_quimby'
                }
            )
        
        return users

    def create_test_delegation_users(self, communities):
        """Create specific test users A, B, C, D, E, F, G, H for delegation testing."""
        test_users = []
        
        for community in communities:
            community_suffix = '_minion' if 'Minion' in community.name else '_springfield'
            
            # Create test users A through H
            test_user_data = [
                ('A' + community_suffix, 'A', 'Test', True),  # Manual voter with tags
                ('B' + community_suffix, 'B', 'Test', False), # Calculated voter
                ('C' + community_suffix, 'C', 'Test', False), # Calculated voter  
                ('D' + community_suffix, 'D', 'Test', False), # Calculated voter
                ('E' + community_suffix, 'E', 'Test', False), # Calculated voter
                ('F' + community_suffix, 'F', 'Test', False), # Calculated voter
                ('G' + community_suffix, 'G', 'Test', False), # Calculated voter
                ('H' + community_suffix, 'H', 'Test', False), # Calculated voter (follows everyone)
            ]
            
            for username, first_name, last_name, is_manual in test_user_data:
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': f'{username.lower()}@test.com',
                        'is_active': True,
                    }
                )
                test_users.append(user)
                
                # Create membership
                Membership.objects.get_or_create(
                    member=user,
                    community=community,
                    defaults={
                        'is_voting_community_member': True,
                        'is_community_manager': False
                    }
                )
                
                self.stdout.write(f'Created test user: {username} in {community.name}')
        
        return test_users

    def create_test_delegation_relationships(self, all_users):
        """Create the specific test delegation pattern as requested by user."""
        for community_name in ['Minion Collective', 'Springfield Town Council']:
            suffix = '_minion' if 'Minion' in community_name else '_springfield'
            
            # Find test users for this community
            try:
                A = User.objects.get(username=f'A{suffix}')
                B = User.objects.get(username=f'B{suffix}')
                C = User.objects.get(username=f'C{suffix}')
                D = User.objects.get(username=f'D{suffix}')
                E = User.objects.get(username=f'E{suffix}')
                F = User.objects.get(username=f'F{suffix}')
                G = User.objects.get(username=f'G{suffix}')
                H = User.objects.get(username=f'H{suffix}')
                
                # Create delegation relationships as specified:
                # B and C follow A. B follows A only on "governance". A always uses "governance" tag.
                Following.objects.get_or_create(
                    follower=B, followee=A,
                    defaults={'tags': 'governance', 'order': 1}
                )
                
                Following.objects.get_or_create(
                    follower=C, followee=A,
                    defaults={'tags': 'governance', 'order': 1}
                )
                
                # E and F are following C. E follows C on governance, F follows C on all tags.
                Following.objects.get_or_create(
                    follower=E, followee=C,
                    defaults={'tags': 'governance', 'order': 1}
                )
                
                Following.objects.get_or_create(
                    follower=F, followee=C,
                    defaults={'tags': '', 'order': 1}  # Empty tags means "all tags"
                )
                
                # G is following A and D
                Following.objects.get_or_create(
                    follower=G, followee=A,
                    defaults={'tags': 'governance', 'order': 1}
                )
                
                Following.objects.get_or_create(
                    follower=G, followee=D,
                    defaults={'tags': '', 'order': 2}  # All tags
                )
                
                # H is following all of them on all tags
                Following.objects.get_or_create(
                    follower=H, followee=A,
                    defaults={'tags': '', 'order': 1}
                )
                
                Following.objects.get_or_create(
                    follower=H, followee=B,
                    defaults={'tags': '', 'order': 2}
                )
                
                Following.objects.get_or_create(
                    follower=H, followee=C,
                    defaults={'tags': '', 'order': 3}
                )
                
                Following.objects.get_or_create(
                    follower=H, followee=D,
                    defaults={'tags': '', 'order': 4}
                )
                
                Following.objects.get_or_create(
                    follower=H, followee=E,
                    defaults={'tags': '', 'order': 5}
                )
                
                Following.objects.get_or_create(
                    follower=H, followee=F,
                    defaults={'tags': '', 'order': 6}
                )
                
                Following.objects.get_or_create(
                    follower=H, followee=G,
                    defaults={'tags': '', 'order': 7}
                )
                
                # ADD CIRCULAR REFERENCE TEST: D follows B (creates potential D→B→A loop)
                Following.objects.get_or_create(
                    follower=D, followee=B,
                    defaults={'tags': 'budget', 'order': 1}
                )
                
                self.stdout.write(f'✅ Created REALISTIC test delegation pattern in {community_name}:')
                self.stdout.write(f'  🎯 A (MANUAL VOTER - seed vote, uses "governance" tag)')
                self.stdout.write(f'  📊 B → A (governance only)')
                self.stdout.write(f'  📊 C → A (governance)')
                self.stdout.write(f'  🔗 E → C → A (2-level chain)')
                self.stdout.write(f'  🔗 F → C → A (2-level chain, all tags)')
                self.stdout.write(f'  🔗🔗 G → A + D (dual inheritance)')
                self.stdout.write(f'  🌳 H → everyone (deep inheritance tree)')
                self.stdout.write(f'  ⚠️ D → B → A (circular prevention test)')
                self.stdout.write(f'  💫 Multi-path deduplication: H→F→C→A + H→C→A = single A vote')
                
            except User.DoesNotExist as e:
                self.stdout.write(f'Could not find test users for {community_name}: {e}')

    def create_multilevel_delegation_chains(self, all_users):
        """Create realistic multi-level delegation chains with diverse tags."""
        # Diverse tag options
        tag_options = [
            'governance', 'budget', 'environment', 'maintenance', 'safety', 
            'events', 'operations', 'policy', 'finance', 'community',
            'transportation', 'recreation', 'education', 'health'
        ]
        
        # Get community-specific users
        minion_users = [u for u in all_users if 'minion' in u.username.lower() or 'gru' in u.username.lower()]
        springfield_users = [u for u in all_users if u not in minion_users]
        
        # Create delegation chains for each community
        self.create_community_delegation_chains(minion_users, tag_options)
        self.create_community_delegation_chains(springfield_users, tag_options)

    def create_community_delegation_chains(self, users, tag_options):
        """Create delegation chains within a community."""
        if len(users) < 15:
            return
            
        # First 10 users are manual voters (leaders)
        manual_voters = users[:10]
        calculated_voters = users[10:25]  # Next 15 are calculated voters
        
        # Create one complex 4-level branching delegation tree
        if len(calculated_voters) >= 8 and len(manual_voters) >= 3:
            # Level 4 (deepest): Bob follows Alice AND Susan (2 manual voters)
            bob = calculated_voters[0]
            alice, susan = manual_voters[0], manual_voters[1]  # 2 manual voters
            
            Following.objects.get_or_create(
                follower=bob,
                followee=alice,
                defaults={'tags': 'budget', 'order': 1}
            )
            Following.objects.get_or_create(
                follower=bob,
                followee=susan,
                defaults={'tags': 'environment', 'order': 2}
            )
            
            # Level 3: Carol and David both follow Bob (so they inherit from Alice+Susan)
            carol, david = calculated_voters[1], calculated_voters[2]
            
            Following.objects.get_or_create(
                follower=carol,
                followee=bob,
                defaults={'tags': 'budget', 'order': 1}
            )
            Following.objects.get_or_create(
                follower=david,
                followee=bob,
                defaults={'tags': 'environment', 'order': 1}
            )
            
            # Level 2: Eve follows Carol AND David (gets both their inheritance trees)
            eve = calculated_voters[3]
            Following.objects.get_or_create(
                follower=eve,
                followee=carol,
                defaults={'tags': 'budget', 'order': 1}
            )
            Following.objects.get_or_create(
                follower=eve,
                followee=david,
                defaults={'tags': 'environment', 'order': 2}
            )
            
            # Level 1: Frank follows Eve (inherits from entire tree: Alice, Susan, Bob, Carol, David)
            frank = calculated_voters[4]
            Following.objects.get_or_create(
                follower=frank,
                followee=eve,
                defaults={'tags': 'budget,environment', 'order': 1}
            )
            
            self.stdout.write(f'Created 4-level BRANCHING tree:')
            self.stdout.write(f'  Level 4: {bob.username} follows {alice.username} + {susan.username}')
            self.stdout.write(f'  Level 3: {carol.username} + {david.username} follow {bob.username}')
            self.stdout.write(f'  Level 2: {eve.username} follows {carol.username} + {david.username}')
            self.stdout.write(f'  Level 1: {frank.username} follows {eve.username} (inherits from 5 people!)')
        
        # Create other realistic delegation relationships
        remaining_calculated = calculated_voters[5:] if len(calculated_voters) > 5 else []
        
        for voter in remaining_calculated:
            # Each voter follows 1-3 people (creating branching, not just chains)
            num_follows = random.randint(1, 3)
            
            # Mix of manual voters and other calculated voters
            potential_followees = manual_voters + [v for v in calculated_voters if v != voter]
            followees = random.sample(potential_followees, min(num_follows, len(potential_followees)))
            
            for i, followee in enumerate(followees):
                tag = random.choice(tag_options)
                Following.objects.get_or_create(
                    follower=voter,
                    followee=followee,
                    defaults={'tags': tag, 'order': i + 1}
                )

    def create_test_decisions(self, communities):
        """Create themed decisions for each community."""
        decisions = []
        
        for community in communities:
            if community.name == 'Minion Collective':
                decision = self.create_minion_decision(community)
            else:
                decision = self.create_springfield_decision(community)
            decisions.append(decision)
            
        return decisions

    def create_minion_decision(self, community):
        """Create a Minion-themed decision."""
        decision, created = Decision.objects.get_or_create(
            community=community,
            title='World Domination Meeting Schedule',
            defaults={
                'description': 'When should we hold our weekly world domination planning meetings? Consider banana snack timing and nap schedules.',
                'dt_close': timezone.now() + timedelta(days=7),
                'results_need_updating': True
            }
        )
        
        if created:
            choices_data = [
                ('Monday 9 AM', 'Early start, fresh bananas available'),
                ('Wednesday 2 PM', 'Post-lunch energy, good for scheming'),
                ('Friday 4 PM', 'End-of-week motivation, weekend planning')
            ]
            
            for title, description in choices_data:
                Choice.objects.get_or_create(
                    decision=decision,
                    title=title,
                    defaults={'description': description}
                )
        
        return decision

    def create_springfield_decision(self, community):
        """Create a Springfield-themed decision."""
        decision, created = Decision.objects.get_or_create(
            community=community,
            title='Nuclear Plant Safety Inspection Schedule', 
            defaults={
                'description': 'How often should we inspect the nuclear power plant for safety violations? Homer promises to stay awake this time.',
                'dt_close': timezone.now() + timedelta(days=7),
                'results_need_updating': True
            }
        )
        
        if created:
            choices_data = [
                ('Daily Inspections', 'Maximum safety, minimum donuts'),
                ('Weekly Inspections', 'Balanced approach, some donuts allowed'),
                ('Monthly Inspections', 'Trust Homer, maximum donuts')
            ]
            
            for title, description in choices_data:
                Choice.objects.get_or_create(
                    decision=decision,
                    title=title,
                    defaults={'description': description}
                )
        
        return decision

    def create_realistic_manual_votes(self, decisions, all_users):
        """Create realistic manual votes - the foundation for delegation."""
        tag_options = [
            'governance', 'budget', 'environment', 'maintenance', 'safety', 
            'events', 'operations', 'policy', 'finance', 'community'
        ]
        
        for decision in decisions:
            choices = list(decision.choices.all())
            community_members = decision.community.get_voting_members()
            
            # REALISTIC SCENARIO: Only ~40% of voting members actually vote manually
            # The rest will either not vote or inherit through delegation
            
            # Guaranteed manual voters (community leaders)
            guaranteed_voters = ['kevin_minion', 'stuart_minion', 'bob_minion', 'gru_leader',
                                'homer_simpson', 'marge_simpson', 'lisa_simpson', 'ned_flanders']
            
            # Test user A always votes manually (the source for delegation chains)  
            test_A_users = ['A_minion', 'A_springfield']
            
            # Select ~40% of remaining members to vote manually
            other_members = [m for m in community_members 
                           if m.username not in guaranteed_voters + test_A_users]
            manual_voters_count = max(3, int(len(other_members) * 0.4))  # At least 3 additional
            random_manual_voters = random.sample(other_members, 
                                                min(manual_voters_count, len(other_members)))
            
            # Combine all manual voters
            all_manual_voters = []
            all_manual_voters.extend([m for m in community_members if m.username in guaranteed_voters])
            all_manual_voters.extend([m for m in community_members if m.username in test_A_users])
            all_manual_voters.extend(random_manual_voters)
            
            for voter in all_manual_voters:
                # Test user A always uses 'governance' tag for delegation testing
                if voter.username.startswith('A_'):
                    tags = ['governance']
                    self.stdout.write(f'  ✓ Test user {voter.username} voting manually with governance tag')
                else:
                    tags = random.sample(tag_options, random.randint(1, 3))
                
                ballot, created = Ballot.objects.get_or_create(
                    decision=decision,
                    voter=voter,
                    defaults={
                        'is_calculated': False,
                        'is_anonymous': random.choice([True, False]),
                        'tags': ','.join(tags)
                    }
                )
                
                if created:
                    # Create realistic star ratings
                    for choice in choices:
                        stars = random.randint(1, 5)  # 1-5 stars (avoid 0 for more realistic data)
                        Vote.objects.get_or_create(
                            choice=choice,
                            ballot=ballot,
                            defaults={'stars': stars}
                        )
            
            manual_count = len(all_manual_voters)
            total_eligible = community_members.count()
            
            self.stdout.write(
                f'  Created {manual_count} manual votes out of {total_eligible} eligible voters '
                f'in {decision.community.name} ({manual_count/total_eligible*100:.1f}% direct participation)'
            )
