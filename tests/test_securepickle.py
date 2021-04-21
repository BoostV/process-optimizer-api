from .context import securepickle
from securepickle import pickleToString, unpickleFromString, get_crypto

def test_pickleToString():
    f = get_crypto()
    encoded = pickleToString("myString", f)
    assert encoded != "myString"

def test_unpickleFromString():
    f = get_crypto()
    encoded = pickleToString("myString", f)
    decoded = unpickleFromString(encoded, f)
    assert decoded == "myString"



