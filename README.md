

To generate graphs using https://django-extensions.readthedocs.io/en/latest/graph_models.html

python manage.py graph_models accounts communities -X BaseModel,MembershipProxy,Group,Permission,AbstractUser,AbstractBaseUser,PermissionsMixin -g -o crowdvote_models.png

