import math, random
from django.shortcuts import _get_queryset


def get_object_or_None(klass, *args, **kwargs):
    """
    Uses get() to return an object or None if the object does not exist.

    klass may be a Model, Manager, or QuerySet object. All other passed
    arguments and keyword arguments are used in the get() query.

    Note: Like with get(), a MultipleObjectsReturned will be raised if more than one
    object is found.
    """
    queryset = _get_queryset(klass)
    try:
        return queryset.get(*args, **kwargs)
    except queryset.model.DoesNotExist:
        return None


def normal_round(n):
    # Who knew rounding is so complicated?!?!  Just implementing it here for now,
    # in case we need to swap in something more sophisticated later.
    if n - math.floor(n) < 0.5:
        return math.floor(n)
    return math.ceil(n)


def get_random_madeup_tags():
    """
    Just makes up some number of random gibberish tags for testing...
    """
    abcs = "abcdefghijklmnopqrstuvwxyz"
    tags = []
    for i in range(random.randint(0, 4)):
        tags.append(random.choice(abcs) * 5)
    return list(set(tags))
