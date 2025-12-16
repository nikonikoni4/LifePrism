import functools

def test_for_state(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(args)
        return func(*args, **kwargs)
    return wrapper

@test_for_state
def test(a=1):
    return 

test(2)