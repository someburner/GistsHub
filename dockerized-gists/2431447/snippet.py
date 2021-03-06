#!/usr/bin/env python
"""
Self-versioning and argument-hashing cache decorator for deterministic functions.
Designed to be extensible and API-compliant with Django and Flask cache backends.

For examples and caveats, see the bottom of the file.

Ted Kaemming: https://github.com/tkaemming
Mike Tigas: https://github.com/mtigas
"""
import functools
import hashlib


def generate_function_key(fn):
    """
    Generates a key for this callable by hashing the bytecode. This appears
    to be deterministic on CPython for trivial implementations, but likely
    is implementation-specific.
    """
    return hashlib.md5(fn.func_code.co_code).hexdigest()


def generate_unique_key(*args, **kwargs):
    """
    Generates a unique key based on the hashed values of all of the passed
    arguments. This makes a pretty bold assumption that the hash() function
    is deterministic, which is (probably) implementation specific.
    """
    hashed_args = ['%s' % hash(arg) for arg in args]
    hashed_kwargs = ['%s ' % hash((key, value)) for (key, value) in kwargs.items()]
    # this is md5 hashed again to avoid the key growing too large for memcached
    return hashlib.md5(':'.join(hashed_args + hashed_kwargs)).hexdigest()


def cached(backend, **kwargs):
    """
    Automagical caching for deterministic functions.

    Supported keyword arguments:
    * key: use a user-defined cache key (not versioned) instead of hashing the
        function's bytecode
    * key_generator: use a user-defined cache key generator instead of using
        `__hash__` on the args/kwargs passed to the callable
    * set_kwargs: keyword arguments passed to the cache backend's `set` method,
        so you can pass timeouts, etc. when setting cached values
    """
    def decorator(fn, key=None, key_generator=None, set_kwargs=None):
        if key is None:
            key = generate_function_key(fn)

        if key_generator is None:
            key_generator = generate_unique_key

        if set_kwargs is None:
            set_kwargs = {}

        @functools.wraps(fn)
        def inner(*args, **kwargs):
            unique_key = '%s:%s' % (key, key_generator(*args, **kwargs))

            # If the value is `None` from the cache, then generate the real
            # value and store it.
            value = backend.get(unique_key)
            if value is None:
                value = fn(*args, **kwargs)
                backend.set(unique_key, value, **set_kwargs)

            return value
        return inner

    return functools.partial(decorator, **kwargs)


if __name__ == '__main__':
    # the underlying cache interface is the same as django and flask, so it 
    # should be reasonably portable. otherwise, you can always write a wrapper
    # that supports the same interface

    class CacheBackend(object):
        def get(self, key, fallback=None):
            raise NotImplementedError

        def set(self, key, value):
            raise NotImplementedError

        def __contains__(self, key):
            raise NotImplementedError


    class DummyCacheBackend(CacheBackend):
        def get(self, key, fallback=None):
            print 'GET', key, len(key)
            return fallback

        def set(self, key, value):
            print 'SET', key, len(key), value
            return None

        def __contains__(self, key):
            print 'HAS', key, len(key)
            return False


    # examples!

    cache = DummyCacheBackend()

    # autogenerated base key, automagical key generator

    @cached(backend=cache)
    def foo(x):
        return x

    print foo('bar')
    print foo('baz')


    # let's say we updated the underlying code for foo...
    # the base key will be implicitly versioned since the underlying function
    # code has been modified. there is no need to update arbitrary versioning
    # numbers in the code or jump through other hoops to make sure the cache
    # only returns the result appropriate for the latest logic

    @cached(backend=cache)
    def foo(x):
        return '%s!' % x

    print foo('bar')
    print foo('baz')


    # allow the definition of the base key

    @cached(backend=cache, key='bar')
    def bar(x):
        return x

    print bar('baz')


    # you can use a really awful hash function if you want to break your code
    # notice that the underlying base key is the same as the first example,
    # since the underlying bytecode is actually the same -- this might save you
    # some cache space if you have two functions that actually do the exact
    # same thing (which would be sort of weird but hey, it's your code)

    @cached(backend=cache, key_generator=lambda x: 1)
    def baz(x):
        return x

    print baz(1)
    print baz(2)
    print baz(3)


    # got 99 problems and hashing unhashable types are all of them

    try:
        print foo([1,2,3])
    except TypeError, e:
        print e  # unhashable type: 'list'

    try:
        print foo({"a": 1, "b": 2})
    except TypeError, e:
        print e  # unhashable type: 'dict'


    # you can also cache values without using the decorator syntax

    def expensive_function(x):
        # assume that this does something that takes forever
        return x + x

    cached_expensive_function = cached(backend=cache)(expensive_function)

    # to call without cache
    print expensive_function(1)

    # to call with cache
    print cached_expensive_function(1)
