# CrowdVote

**The Democracy App: A platform for Free-Market Representation**

[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-5.0+-green.svg)](https://www.djangoproject.com/)
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)

## Table of Contents

- [Overview](#overview)
- [The CrowdVote Vision](#the-crowdvote-vision)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Project Goals](#project-goals)
- [Contributing](#contributing)
- [Looking for Communities](#looking-for-communities)
- [License](#license)

## Overview

CrowdVote is a Django-based web application that enables communities to make decisions together through a revolutionary voting system that combines **instant runoff voting** with **delegative democracy**. Unlike traditional voting systems, CrowdVote allows community members to either vote directly on issues or delegate their voting power to trusted members on specific topics through a tagging system.

**TL;DR**: CrowdVote unlocks representation from fixed electoral terms by creating a free market where community members can:
- Vote directly on each referendum
- Delegate their vote to other members they trust on specific topics
- Compete to earn and retain that trust

## The CrowdVote Vision

For several years now, I've been daydreaming about building a free and Open Source web application to help people make decisions together. And I have two questions for you:

Could you use this?
What would you change?

I call it "CrowdVote", and it brings a process I've been calling Social Democracy (as in "Social Media" …not the political ideology) to local communities such as condo associations, town councils, student governments, and anywhere else you might want to "crowdsource" decisions to a community of people.

Unlike a conventional, web-based polling application however, CrowdVote allows community members to then delegate their votes on to an Instant Runoff between one or more other members whose judgement they trust, whenever - and, specifically, on whichever issues they like.

This is done through tagging the decisions you are voting on with terms like "budget" or "environment", which allows other members of the community who trust your judgement on such issues, to then follow you (inherit your votes) on those tags.

Because votes (and their tags) are transitive, the people from whom you inherit your votes may be inheriting theirs from someone else, and they from someone else, and so on.

Trees of influence can emerge organically and evolve to more accurately reflect community sentiment in real time, rather than only once every election cycle.

**…because Real Democracy happens between elections.**

A concrete example: say a condo board will decide next Tuesday what color to paint the community room.

Mary is a board member, and wants to crowdsource her decision on CrowdVote, along with any specific color choices, whether or not folks can write in their own colors, supporting documentation like color codes/swatches, contractor proposals, etc…

Her neighbor Jack sees Mary's published question, and responds by casting a Ranked Choice ballot: [ 'Cathedral Gray', 'Aqua Chiffon', 'Oceanside' ]. And if Jack wants to encourage other members of the community to follow him (again, to inherit his ballot) …he'll want to take a moment to further tag Mary's decision with terms he feels characterize her question and, more importantly, on which others in the community can follow him: [ "maintenance", "beautification", "community room" ].

Now, if their neighbor Sophia is out of town or fails to cast a ballot before next Tuesday for whatever reason, CrowdVote can attempt to calculate a ballot on her behalf …but only if she has previously identified in her profile other community members whose judgement she trusts sufficiently to follow their positions on decisions like this one. Moreover, she may be inheriting votes from lots of people, on a variety of matters. She may follow Mary on "environmental" issues, Jack on "maintenance" and "budget," and also Susan on "budget". …CrowdVote just figures out who's following whom, on which issues, and runs them all through an Instant Runoff to come up with Sophia's ballot, which she is of course free to override anytime before Tuesday by logging in to CrowdVote and casting her own.

**CrowdVote = Free Market Representation.**

…Rather than tying Representation to a fixed term in office, CrowdVote does something not unlike what Social Media has done to traditional media: it gives everyone a voice, even if it's only a re-tweet, +1, Pin or a Like, …all of which are functionally analogous, in the CrowdVote marketplace, to inheriting a vote.

People seeking to expand their influence in the community, like Jack above, will compete for followers by voting and tagging decisions thoughtfully, perhaps in conjunction with blogging and tweeting or otherwise promoting a reputation for expertise in the issues they care about. Lobbyists will turn their attention to those members with the most followers at any given time. Nobody has to wait until the next election to be heard. And all of this happens right out of the gate, because when you first fire CrowdVote up and begin publishing decisions to be voted on, your constituents will all effectively default to inheriting your vote, leaving you in a position of voting in accordance with the wishes of people who are all just inheriting your vote…but who are all free now to cast their own vote, or to follow someone else. They're not stuck with you until the next election!

Now, CrowdVote won't be able to enforce being used in any particular way. If you run for office on the pledge to CrowdVote all your decisions and then neglect to do so, or if your community decides to use CrowdVote itself in lieu of electing representatives at all, CrowdVote has no way to follow up on what happens after a decision's voting period closes. What CrowdVote can do, however, is make all data completely transparent and easily queried and audited through a friendly REST-ful API. Anyone can re-run the numbers anytime they like. And the calculation and tallying of every ballot is easily delineated in verbose tally reports. Finally, CrowdVote also provides a mechanism to verify everyone's membership in the community, while preserving the anonymity of the relationship between their identity and their voting record, thereby allowing voters to remain anonymous, if they like.

…I really appreciate any feedback or words of encouragement at jason@CrowdVote.com, @CrowdVote or Facebook/CrowdVote! Beyond just being Open Sourced, I'd love to see this built such that any non-technical community leader could just deploy their own instance to the cloud with a simple click of a button. For now, I'm slowly building this thing between work and family, but figured I oughta get the idea out there and protected for everyone under:

CrowdVote and all ideas expressed above by Jason Blum are licensed under a Creative Commons Attribution-ShareAlike 4.0 International License.

## Key Features

### Core Functionality
- **STAR Voting**: Score Then Automatic Runoff voting system
- **Delegative Democracy**: Delegate your vote to trusted members on specific topics
- **Tag-Based Following**: Follow different people for different topics (e.g., follow Alice on "budget", Bob on "environment")
- **Transitive Voting**: Inherit votes through chains of trust
- **Vote Override**: Always maintain the ability to cast your own vote directly
- **Anonymous Voting**: Optional anonymity while maintaining verifiable membership

### Technical Features
- **Multi-Community Support**: Host multiple communities on a single instance
- **Transparent API**: RESTful API for complete data transparency and auditability
- **Detailed Tally Reports**: Verbose logging of all vote calculations
- **Member Verification**: Secure membership verification system
- **One-Click Deploy**: Simple deployment for non-technical users (coming soon)

## Tech Stack

### Core Technologies
- **Backend**: Django 5.0+
- **Database**: PostgreSQL
- **Styling**: Tailwind CSS
- **Container**: Docker
- **Deployment**: Railway
- **Version Control**: GitHub

### Key Django Packages
- **django-allauth**: Authentication and registration
- **django-service-objects**: Service layer for business logic
- **django-taggit**: Tagging system for issue categorization
- **django-extensions**: Development utilities
- **django-debug-toolbar**: Development debugging

## Installation

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Docker (optional but recommended)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/crowdvote.git
   cd crowdvote
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install uv and dependencies**
   ```bash
   # Install uv (fast Python package installer)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # Or via Homebrew: brew install uv
   
   # Install dependencies
   uv pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and secret key
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Load sample data (optional)**
   ```bash
   python manage.py loaddata fixtures/sample_community.json
   ```

8. **Run the development server**
   ```bash
   python manage.py runserver
   ```

### Docker Setup

```bash
docker-compose up --build
```

## Project Goals

### 1. Live Demo with Minions 🎬
We're building a fun, interactive demonstration where Minions vote on their daily lunch choices. This simulation will showcase:
- Real-time voting and delegation
- Dynamic vote inheritance trees
- Daily referendums (what sandwich for lunch?)
- Visual representation of democratic emergence

Visit the live demo to see democracy in action!

### 2. One-Click Deploy 🚀
Making CrowdVote accessible to non-technical community leaders through:
- Railway deploy button
- Automated setup wizard
- Pre-configured templates for different community types
- Zero technical knowledge required

### 3. Real-World Implementation 🏘️
Actively seeking partnerships with:
- **Condo Associations**: Building maintenance, budget decisions, community rules
- **Town Councils**: Local ordinances, budget allocation, community projects
- **Student Governments**: Campus policies, event planning, budget distribution
- **Co-ops and Collectives**: Operational decisions, member policies
- **Small Organizations**: Teams of 50-500 people making regular decisions

## Contributing

We welcome contributions from developers, designers, and democracy enthusiasts!

### How to Contribute
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Areas We Need Help
- **Frontend Development**: Improving the UI/UX with Tailwind CSS
- **Visualization**: Creating engaging real-time vote visualization
- **Testing**: Writing comprehensive test suites
- **Documentation**: Improving docs and creating tutorials
- **Community Outreach**: Finding real communities to pilot the platform

### Development Guidelines
- Follow Django best practices
- Write tests for new features
- Keep commits atomic and well-described
- Update documentation as needed
- Maintain docs/CHANGELOG.md with development session history

## Looking for Communities

**Are you part of a community that makes decisions together?**

We're actively seeking communities to collaborate with for real-world testing and implementation. Ideal communities:
- Have 50-500 members
- Make regular decisions together
- Want more democratic participation
- Are open to trying new approaches

If this sounds like your community, please reach out to jason@CrowdVote.com

## Support

- **Email**: jason@CrowdVote.com
- **Twitter**: [@CrowdVote](https://twitter.com/CrowdVote)
- **Facebook**: [Facebook/CrowdVote](https://facebook.com/CrowdVote)
- **Issues**: [GitHub Issues](https://github.com/yourusername/crowdvote/issues)

## License

This project is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Real Democracy happens between elections.</strong><br>
  Built with ❤️ for communities everywhere
</p>