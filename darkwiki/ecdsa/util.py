import sys
import time

bfh = bytes.fromhex

def bh2u(x):
    """
    str with hex representation of a bytes-like object

    >>> x = bytes((1, 2, 10))
    >>> bh2u(x)
    '01020A'

    :param x: bytes
    :rtype: str
    """
    return hfu(x).decode('ascii')

def assert_bytes(*args):
    """
    porting helper, assert args type
    """
    try:
        for x in args:
            assert isinstance(x, (bytes, bytearray))
    except:
        print('assert bytes failed', list(map(type, args)))
        raise

is_verbose = True
def set_verbosity(b):
    global is_verbose
    is_verbose = b


def print_error(*args):
    if not is_verbose: return
    print_stderr(*args)

def print_stderr(*args):
    args = [str(item) for item in args]
    sys.stderr.write(" ".join(args) + "\n")
    sys.stderr.flush()

def to_bytes(something, encoding='utf8'):
    """
    cast string to bytes() like object, but for python2 support it's bytearray copy
    """
    if isinstance(something, bytes):
        return something
    if isinstance(something, str):
        return something.encode(encoding)
    elif isinstance(something, bytearray):
        return bytes(something)
    else:
        raise TypeError("Not a string or bytes like object")

def to_string(x, enc):
    if isinstance(x, (bytes, bytearray)):
        return x.decode(enc)
    if isinstance(x, str):
        return x
    else:
        raise TypeError("Not a string or bytes like object")

class InvalidPassword(Exception):
    def __str__(self):
        return "Incorrect password"

# decorator that prints execution time
def profiler(func):
    def do_profile(func, args, kw_args):
        n = func.__name__
        t0 = time.time()
        o = func(*args, **kw_args)
        t = time.time() - t0
        print_error("[profiler]", n, "%.4f"%t)
        return o
    return lambda *args, **kw_args: do_profile(func, args, kw_args)

