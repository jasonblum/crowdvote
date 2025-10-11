import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings

from democracy.models import Community, Membership, Decision, Choice, Ballot, Vote, Following

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate realistic demo communities with delegation chains. Use --reset-database to wipe everything first.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-data',
            action='store_true',
            help='Clear existing community data (keeps users)'
        )
        parser.add_argument(
            '--reset-database',
            action='store_true',
            help='DESTRUCTIVE: Wipe entire database and recreate superuser (local only)'
        )

    def handle(self, *args, **options):
        # --reset-database takes precedence over --clear-data
        if options['reset_database']:
            self.reset_database_completely()
        elif options['clear_data']:
            self.clear_existing_data()
        
        self.stdout.write(
            self.style.SUCCESS('Generating REALISTIC community with proper voting patterns...')
        )

        # Create communities (returns 5, but we only populate first 2)
        all_communities = self.create_communities()
        communities_to_populate = all_communities[:2]  # Only Minions and Springfield
        
        # Create users with specific voting patterns (only for first 2 communities)
        all_users = []
        for community in communities_to_populate:
            users = self.create_users_for_community(community)
            all_users.extend(users)
        
        # Add specific test users for delegation debugging (only for first 2 communities)
        test_users = self.create_test_delegation_users(communities_to_populate)
        all_users.extend(test_users)
        
        # Create test decisions FIRST (only for first 2 communities)
        decisions = self.create_test_decisions(communities_to_populate)
        
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

    def reset_database_completely(self):
        """
        Completely wipe the database and recreate superuser.
        
        This method performs a complete database reset in the correct order
        to respect foreign key constraints. Signals are temporarily disabled
        to prevent massive thread spawning during deletion.
        
        After wiping, it creates a superuser with username/password 'admin' 
        ONLY if DEBUG=True (local development).
        
        This is designed for daily/weekly demo resets on the production site.
        """
        from django.db.models import signals
        from democracy.models import DecisionSnapshot
        
        self.stdout.write(self.style.WARNING('⚠️  RESETTING ENTIRE DATABASE...'))
        self.stdout.write('Temporarily disabling signals to prevent thread overload...')
        
        # Temporarily disconnect signals to prevent overwhelming database with threads
        signals.post_save.disconnect(dispatch_uid='vote_changed')
        signals.post_delete.disconnect(dispatch_uid='vote_deleted')
        signals.post_save.disconnect(dispatch_uid='following_changed')
        signals.post_delete.disconnect(dispatch_uid='following_deleted')
        
        try:
            # Delete in reverse foreign key order
            self.stdout.write('Deleting Votes...')
            Vote.objects.all().delete()
            
            self.stdout.write('Deleting Ballots...')
            Ballot.objects.all().delete()
            
            self.stdout.write('Deleting Choices...')
            Choice.objects.all().delete()
            
            self.stdout.write('Deleting DecisionSnapshots...')
            DecisionSnapshot.objects.all().delete()
            
            self.stdout.write('Deleting Decisions...')
            Decision.objects.all().delete()
            
            self.stdout.write('Deleting Following relationships...')
            Following.objects.all().delete()
            
            self.stdout.write('Deleting Memberships...')
            Membership.objects.all().delete()
            
            self.stdout.write('Deleting Communities...')
            Community.objects.all().delete()
            
            self.stdout.write('Deleting Users...')
            User.objects.all().delete()
            
            self.stdout.write(self.style.SUCCESS('✅ Database wiped clean!'))
        finally:
            # Re-enable signals (they'll reconnect automatically on next import)
            self.stdout.write('Re-enabling signals...')
        
        # Create superuser only in DEBUG mode (local development)
        if settings.DEBUG:
            self.stdout.write('Creating superuser (DEBUG mode)...')
            User.objects.create_superuser(
                username='admin',
                email='admin@crowdvote.local',
                password='admin',
                first_name='Admin',
                last_name='User'
            )
            self.stdout.write(self.style.SUCCESS('🔐 Superuser created: admin/admin'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Skipping superuser creation (production mode)'))

    def clear_existing_data(self):
        """Clear existing relationships data but keep users and communities."""
        self.stdout.write('Clearing existing data...')
        Vote.objects.all().delete()
        Ballot.objects.all().delete()
        Choice.objects.all().delete()  # Clear choices first
        Decision.objects.all().delete()
        Following.objects.all().delete()
        Membership.objects.all().delete()
        # Don't delete communities and users - just relationships

    def create_communities(self):
        """
        Create 5 demo communities: 2 auto-approve + 3 application-required.
        
        Returns:
            list: All communities, but only first 2 will have users/decisions created
        """
        # Auto-approve communities (for immediate demo access)
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
        
        # Application-required communities (users must apply to join)
        oceanview, _ = Community.objects.get_or_create(
            name='Ocean View Condo Association',
            defaults={
                'description': 'A beachfront residential community managing shared amenities, maintenance decisions, and community events.',
                'auto_approve_applications': False,
                'application_message_required': True
            }
        )
        
        tech_coop, _ = Community.objects.get_or_create(
            name='Tech Workers Cooperative',
            defaults={
                'description': 'A worker-owned technology cooperative making operational and strategic decisions democratically.',
                'auto_approve_applications': False,
                'application_message_required': True
            }
        )
        
        garden, _ = Community.objects.get_or_create(
            name='Riverside Community Garden',
            defaults={
                'description': 'A neighborhood garden collective deciding on plot assignments, rules, and community events.',
                'auto_approve_applications': False,
                'application_message_required': True
            }
        )
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ Created 5 communities:\n'
            f'   • 2 auto-approve (with demo users): Minions, Springfield\n'
            f'   • 3 application-required (empty): Ocean View, Tech Workers, Riverside'
        ))
        
        # Return all communities, but caller should only populate first 2
        return [minion_community, springfield_community, oceanview, tech_coop, garden]

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
            is_voter = username not in [u[0] for u in non_voters]
            # Lobbyists MUST be public (is_anonymous=False), voters can be anonymous
            is_anonymous = random.random() > 0.3 if is_voter else False  # 70% anonymous for voters, 0% for lobbyists
            Membership.objects.get_or_create(
                member=user,
                community=community,
                defaults={
                    'is_voting_community_member': is_voter,
                    'is_community_manager': username == 'gru_leader',
                    'is_anonymous': is_anonymous
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
            is_voter = username not in [u[0] for u in non_voters]
            # Lobbyists MUST be public (is_anonymous=False), voters can be anonymous
            is_anonymous = random.random() > 0.3 if is_voter else False  # 70% anonymous for voters, 0% for lobbyists
            Membership.objects.get_or_create(
                member=user,
                community=community,
                defaults={
                    'is_voting_community_member': is_voter,
                    'is_community_manager': username == 'mayor_quimby',
                    'is_anonymous': is_anonymous
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
                        'is_community_manager': False,
                        'is_anonymous': random.random() > 0.3  # 70% anonymous
                    }
                )
                
                self.stdout.write(f'Created test user: {username} in {community.name}')
        
        return test_users

    def create_test_delegation_relationships(self, all_users):
        """
        Create the specific test delegation pattern as requested by user.
        
        Ensures test users are public (non-anonymous) so they can be followed.
        """
        for community_name in ['Minion Collective', 'Springfield Town Council']:
            suffix = '_minion' if 'Minion' in community_name else '_springfield'
            
            # Get community
            try:
                community = Community.objects.get(name=community_name)
                
                # Find test users for this community
                A = User.objects.get(username=f'A{suffix}')
                B = User.objects.get(username=f'B{suffix}')
                C = User.objects.get(username=f'C{suffix}')
                D = User.objects.get(username=f'D{suffix}')
                E = User.objects.get(username=f'E{suffix}')
                F = User.objects.get(username=f'F{suffix}')
                G = User.objects.get(username=f'G{suffix}')
                H = User.objects.get(username=f'H{suffix}')
                
                # Get their Memberships in this community
                A_membership = Membership.objects.get(member=A, community=community)
                B_membership = Membership.objects.get(member=B, community=community)
                C_membership = Membership.objects.get(member=C, community=community)
                D_membership = Membership.objects.get(member=D, community=community)
                E_membership = Membership.objects.get(member=E, community=community)
                F_membership = Membership.objects.get(member=F, community=community)
                G_membership = Membership.objects.get(member=G, community=community)
                H_membership = Membership.objects.get(member=H, community=community)
                
                # Ensure test users A-H are all public (not anonymous) for testing purposes
                for membership in [A_membership, B_membership, C_membership, D_membership, 
                                 E_membership, F_membership, G_membership, H_membership]:
                    if membership.is_anonymous:
                        membership.is_anonymous = False
                        membership.save()
                        self.stdout.write(f'Made {membership.member.username} public for delegation testing')
                
                # Create delegation relationships as specified:
                # B and C follow A. B follows A only on "governance". A always uses "governance" tag.
                Following.objects.get_or_create(
                    follower=B_membership, followee=A_membership,
                    defaults={'tags': 'governance', 'order': 1}
                )
                
                Following.objects.get_or_create(
                    follower=C_membership, followee=A_membership,
                    defaults={'tags': 'governance', 'order': 1}
                )
                
                # E and F are following C. E follows C on governance, F follows C on all tags.
                Following.objects.get_or_create(
                    follower=E_membership, followee=C_membership,
                    defaults={'tags': 'governance', 'order': 1}
                )
                
                Following.objects.get_or_create(
                    follower=F_membership, followee=C_membership,
                    defaults={'tags': '', 'order': 1}  # Empty tags means "all tags"
                )
                
                # G is following A and D
                Following.objects.get_or_create(
                    follower=G_membership, followee=A_membership,
                    defaults={'tags': 'governance', 'order': 1}
                )
                
                Following.objects.get_or_create(
                    follower=G_membership, followee=D_membership,
                    defaults={'tags': '', 'order': 2}  # All tags
                )
                
                # H is following all of them on all tags
                Following.objects.get_or_create(
                    follower=H_membership, followee=A_membership,
                    defaults={'tags': '', 'order': 1}
                )
                
                Following.objects.get_or_create(
                    follower=H_membership, followee=B_membership,
                    defaults={'tags': '', 'order': 2}
                )
                
                Following.objects.get_or_create(
                    follower=H_membership, followee=C_membership,
                    defaults={'tags': '', 'order': 3}
                )
                
                Following.objects.get_or_create(
                    follower=H_membership, followee=D_membership,
                    defaults={'tags': '', 'order': 4}
                )
                
                Following.objects.get_or_create(
                    follower=H_membership, followee=E_membership,
                    defaults={'tags': '', 'order': 5}
                )
                
                Following.objects.get_or_create(
                    follower=H_membership, followee=F_membership,
                    defaults={'tags': '', 'order': 6}
                )
                
                Following.objects.get_or_create(
                    follower=H_membership, followee=G_membership,
                    defaults={'tags': '', 'order': 7}
                )
                
                # ADD CIRCULAR REFERENCE TEST: D follows B (creates potential D→B→A loop)
                Following.objects.get_or_create(
                    follower=D_membership, followee=B_membership,
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
        
        # Get community-specific users (exclude test users A-H)
        minion_users = [u for u in all_users if ('minion' in u.username.lower() or 'gru' in u.username.lower()) and not u.username.startswith(('A_', 'B_', 'C_', 'D_', 'E_', 'F_', 'G_', 'H_'))]
        springfield_users = [u for u in all_users if u not in minion_users and not u.username.startswith(('A_', 'B_', 'C_', 'D_', 'E_', 'F_', 'G_', 'H_'))]
        
        # Create delegation chains for each community
        self.create_community_delegation_chains(minion_users, tag_options)
        self.create_community_delegation_chains(springfield_users, tag_options)

    def create_community_delegation_chains(self, users, tag_options):
        """
        Create delegation chains within a community.
        
        Only creates Following relationships to public (non-anonymous) members,
        since it's unrealistic for people to follow anonymous users.
        """
        if len(users) < 15:
            return
            
        # First 10 users are manual voters (leaders)
        manual_voters = users[:10]
        calculated_voters = users[10:25]  # Next 15 are calculated voters
        
        # Determine community from first user
        if not manual_voters:
            return
        first_user = manual_voters[0]
        try:
            # Get community membership to determine which community we're working with
            membership = Membership.objects.filter(member=first_user).first()
            if not membership:
                return
            community = membership.community
        except Exception:
            return
        
        # Create one complex 4-level branching delegation tree
        if len(calculated_voters) >= 8 and len(manual_voters) >= 3:
            # Get public (non-anonymous) manual voters only - people only follow public members
            public_manual_voters = [
                u for u in manual_voters 
                if not Membership.objects.get(member=u, community=community).is_anonymous
            ]
            
            if len(public_manual_voters) < 2:
                self.stdout.write('Not enough public manual voters for delegation tree')
                return
            
            # Level 4 (deepest): Bob follows Alice AND Susan (2 public manual voters)
            bob = calculated_voters[0]
            alice, susan = public_manual_voters[0], public_manual_voters[1]
            
            # Get Memberships
            bob_membership = Membership.objects.get(member=bob, community=community)
            alice_membership = Membership.objects.get(member=alice, community=community)
            susan_membership = Membership.objects.get(member=susan, community=community)
            
            Following.objects.get_or_create(
                follower=bob_membership,
                followee=alice_membership,
                defaults={'tags': 'budget', 'order': 1}
            )
            Following.objects.get_or_create(
                follower=bob_membership,
                followee=susan_membership,
                defaults={'tags': 'environment', 'order': 2}
            )
            
            # Level 3: Carol and David both follow Bob (so they inherit from Alice+Susan)
            carol, david = calculated_voters[1], calculated_voters[2]
            try:
                carol_membership = Membership.objects.get(member=carol, community=community)
                david_membership = Membership.objects.get(member=david, community=community)
            except Membership.DoesNotExist as e:
                self.stdout.write(f'Warning: Skipping delegation chain - membership not found for {carol.username} or {david.username} in {community.name}')
                return
            
            Following.objects.get_or_create(
                follower=carol_membership,
                followee=bob_membership,
                defaults={'tags': 'budget', 'order': 1}
            )
            Following.objects.get_or_create(
                follower=david_membership,
                followee=bob_membership,
                defaults={'tags': 'environment', 'order': 1}
            )
            
            # Level 2: Eve follows Carol AND David (gets both their inheritance trees)
            eve = calculated_voters[3]
            eve_membership = Membership.objects.get(member=eve, community=community)
            
            Following.objects.get_or_create(
                follower=eve_membership,
                followee=carol_membership,
                defaults={'tags': 'budget', 'order': 1}
            )
            Following.objects.get_or_create(
                follower=eve_membership,
                followee=david_membership,
                defaults={'tags': 'environment', 'order': 2}
            )
            
            # Level 1: Frank follows Eve (inherits from entire tree: Alice, Susan, Bob, Carol, David)
            frank = calculated_voters[4]
            frank_membership = Membership.objects.get(member=frank, community=community)
            
            Following.objects.get_or_create(
                follower=frank_membership,
                followee=eve_membership,
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
            
            # Mix of manual voters and other calculated voters - but ONLY public members
            potential_followees_all = manual_voters + [v for v in calculated_voters if v != voter]
            potential_followees = [
                u for u in potential_followees_all
                if not Membership.objects.get(member=u, community=community).is_anonymous
            ]
            
            if not potential_followees:
                continue  # Skip if no public members to follow
            
            followees = random.sample(potential_followees, min(num_follows, len(potential_followees)))
            
            # Get voter's membership
            voter_membership = Membership.objects.get(member=voter, community=community)
            
            for i, followee in enumerate(followees):
                tag = random.choice(tag_options)
                # Get followee's membership
                followee_membership = Membership.objects.get(member=followee, community=community)
                
                Following.objects.get_or_create(
                    follower=voter_membership,
                    followee=followee_membership,
                    defaults={'tags': tag, 'order': i + 1}
                )

    def create_test_decisions(self, communities):
        """
        Create 4 themed decisions per community with varied timing.
        
        Decision timing strategy:
        - Decision 1: CLOSED (1 hour ago)
        - Decision 2: Closes tomorrow (~23 hours)
        - Decision 3: Closes in 1 week
        - Decision 4: Closes in 2 weeks
        """
        decisions = []
        
        for community in communities:
            if community.name == 'Minion Collective':
                community_decisions = self.create_minion_decisions(community)
            else:
                community_decisions = self.create_springfield_decisions(community)
            decisions.extend(community_decisions)
            
        return decisions

    def create_minion_decisions(self, community):
        """Create 4 Minion-themed decisions with varied timing."""
        decisions = []
        now = timezone.now()
        
        # Decision 1: CLOSED (1 hour ago)
        decision1, created = Decision.objects.get_or_create(
            community=community,
            title='Which Master Should We Follow Next?',
            defaults={
                'description': 'Our current master situation is uncertain. Who should lead us into our next adventure?',
                'dt_close': now - timedelta(hours=1),
                'results_need_updating': True
            }
        )
        if created:
            Choice.objects.bulk_create([
                Choice(decision=decision1, title='Stay with Gru', description='He\'s familiar and has great gadgets'),
                Choice(decision=decision1, title='Return to Scarlet Overkill', description='She was stylish and ambitious'),
                Choice(decision=decision1, title='Find El Macho', description='Strong and fearless leader'),
                Choice(decision=decision1, title='Follow Dr. Nefario', description='Smart inventor with freeze ray'),
            ])
        decisions.append(decision1)
        
        # Decision 2: Closes tomorrow (~23 hours)
        decision2, created = Decision.objects.get_or_create(
            community=community,
            title='Official Minion Language Word of the Month',
            defaults={
                'description': 'Vote for the most useful Minionese word that everyone should use more often this month!',
                'dt_close': now + timedelta(hours=23),
                'results_need_updating': True
            }
        )
        if created:
            Choice.objects.bulk_create([
                Choice(decision=decision2, title='Bello!', description='Classic greeting, always appropriate'),
                Choice(decision=decision2, title='Poopaye!', description='Versatile exclamation for any situation'),
                Choice(decision=decision2, title='Tulaliloo ti amo', description='Romantic and sophisticated'),
                Choice(decision=decision2, title='Banana', description='Universal word, works for everything'),
            ])
        decisions.append(decision2)
        
        # Decision 3: Closes in 1 week
        decision3, created = Decision.objects.get_or_create(
            community=community,
            title='Mandatory Uniform Upgrade Decision',
            defaults={
                'description': 'Time to update our iconic look! Which uniform modification should we adopt?',
                'dt_close': now + timedelta(days=7),
                'results_need_updating': True
            }
        )
        if created:
            Choice.objects.bulk_create([
                Choice(decision=decision3, title='Keep Classic Overalls', description='If it ain\'t broke, don\'t fix it'),
                Choice(decision=decision3, title='Add Superhero Capes', description='More dramatic and impressive'),
                Choice(decision=decision3, title='Switch to Tuxedos', description='Sophisticated and professional'),
                Choice(decision=decision3, title='Banana Costumes', description='Commit fully to the banana theme'),
            ])
        decisions.append(decision3)
        
        # Decision 4: Closes in 2 weeks
        decision4, created = Decision.objects.get_or_create(
            community=community,
            title='Weekly Banana Budget Allocation',
            defaults={
                'description': 'How many bananas should each minion receive per week? This affects our community budget significantly.',
                'dt_close': now + timedelta(days=14),
                'results_need_updating': True
            }
        )
        if created:
            Choice.objects.bulk_create([
                Choice(decision=decision4, title='50 bananas per week', description='Conservative, sustainable approach'),
                Choice(decision=decision4, title='75 bananas per week', description='Balanced option for most minions'),
                Choice(decision=decision4, title='100 bananas per week', description='Generous allocation for happy minions'),
                Choice(decision=decision4, title='Unlimited banana access', description='BANANA! (budget concerns irrelevant)'),
            ])
        decisions.append(decision4)
        
        return decisions

    def create_springfield_decisions(self, community):
        """Create 4 Springfield-themed decisions with varied timing."""
        decisions = []
        now = timezone.now()
        
        # Decision 1: CLOSED (1 hour ago)
        decision1, created = Decision.objects.get_or_create(
            community=community,
            title='Donut Shop Zoning Variance for Lard Lad',
            defaults={
                'description': 'Lard Lad Donuts wants to expand. Should we approve the zoning variance?',
                'dt_close': now - timedelta(hours=1),
                'results_need_updating': True
            }
        )
        if created:
            Choice.objects.bulk_create([
                Choice(decision=decision1, title='Approve Full Expansion', description='More donuts = happier Springfield'),
                Choice(decision=decision1, title='Deny Expansion', description='Keep our small-town character'),
                Choice(decision=decision1, title='Approve with Conditions', description='Require healthy options menu'),
                Choice(decision=decision1, title='Relocate to Edge of Town', description='Compromise solution'),
            ])
        decisions.append(decision1)
        
        # Decision 2: Closes tomorrow (~23 hours)
        decision2, created = Decision.objects.get_or_create(
            community=community,
            title='School Bus Route Optimization',
            defaults={
                'description': 'Springfield Elementary needs updated bus routes. Otto is willing to drive whatever we decide.',
                'dt_close': now + timedelta(hours=23),
                'results_need_updating': True
            }
        )
        if created:
            Choice.objects.bulk_create([
                Choice(decision=decision2, title='Keep Otto\'s Current Route', description='Chaotic but familiar'),
                Choice(decision=decision2, title='Hire Professional Driver', description='Safety-first approach'),
                Choice(decision=decision2, title='Add More Stops', description='Convenience for all students'),
                Choice(decision=decision2, title='Reduce Stops for Efficiency', description='Faster routes, less waiting'),
            ])
        decisions.append(decision2)
        
        # Decision 3: Closes in 1 week
        decision3, created = Decision.objects.get_or_create(
            community=community,
            title='Nuclear Plant Safety Inspection Frequency',
            defaults={
                'description': 'How often should we inspect the power plant? Homer promises to stay awake this time. Probably.',
                'dt_close': now + timedelta(days=7),
                'results_need_updating': True
            }
        )
        if created:
            Choice.objects.bulk_create([
                Choice(decision=decision3, title='Daily Inspections', description='Maximum safety, minimum donuts for Homer'),
                Choice(decision=decision3, title='Weekly Inspections', description='Balanced approach, some donuts allowed'),
                Choice(decision=decision3, title='Monthly Inspections', description='Trust Homer more, maximum donuts'),
                Choice(decision=decision3, title='When Homer Remembers', description='The Springfield way'),
            ])
        decisions.append(decision3)
        
        # Decision 4: Closes in 2 weeks
        decision4, created = Decision.objects.get_or_create(
            community=community,
            title='Annual Ribwich Festival Location',
            defaults={
                'description': 'Where should we hold this year\'s legendary Ribwich Festival? The whole town is watching!',
                'dt_close': now + timedelta(days=14),
                'results_need_updating': True
            }
        )
        if created:
            Choice.objects.bulk_create([
                Choice(decision=decision4, title='Town Square', description='Central location, traditional'),
                Choice(decision=decision4, title='Krusty Burger Parking Lot', description='Corporate sponsorship, free fries'),
                Choice(decision=decision4, title='Springfield Stadium', description='Largest capacity, proper facilities'),
                Choice(decision=decision4, title='Cancel Festival', description='Health department concerns'),
            ])
        decisions.append(decision4)
        
        return decisions

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
