# The Democracy App: A platform for Free-Market Representation.


**TLDR**: This app aims to provide a platform for unlocking `Representation` from the arbitrarily fixed terms of a 
community's candidates, by allowing candidates to run on the simple pledge to `CrowdVote` their decisions to 
`Free Market` competition between community `Members`, who are free to 
1) vote directly on each decision, 
2) delegate their vote on to other members whose judgement they trust on whatever topics they like,
3) ...compete with each other to earn and retain that trust!

Read more at https://crowdvote.com/

---

### Documentation

- To generate graphs using https://django-extensions.readthedocs.io/en/latest/graph_models.html <br/>
  `python manage.py graph_models accounts communities -X BaseModel,MembershipProxy,Group,Permission,AbstractUser,AbstractBaseUser,PermissionsMixin -g -o crowdvote_models.png`
- [Django Admin Docs](https://docs.djangoproject.com/en/4.0/ref/contrib/admin/admindocs/) are enabled. 

### Running the app

- Install the requirements: `pip install -r requirements.txt`
- Setup the database with dummy data: `python manage.py reset_database`
<br/>Note: this will also call `populate_database` to set up a bunch of dummy data
- This include a superuser login: *admin*/*admin*
- `python manage.py runserver` and browse to http://127.0.0.1:8000/admin/

### Next steps
1. Need an API with Django Rest Framework
1. Need a Vue.js front-end
1. Need tests