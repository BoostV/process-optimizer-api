from optimizerapi.securepickle import *
import pickle

def test_pickleToString():
    encoded = pickleToString("myString")
    assert encoded != "myString"

def test_unpickleFromString():
    encoded = pickleToString("myString")
    decoded = unpickleFromString(encoded)
    assert decoded == "myString"

# def test_load_key():
#     create_key()
#     key = load_key()
#     assert key != ""
#     assert len(key) == 44

# def test_encrypt():
#     create_key()
#     key = load_key()
#     f = Fernet(key)
#     encoded = pickle.dumps("myString")
#     encrypted = f.encrypt(encoded)
#     assert encoded != encrypted
#     assert type(encrypted) == str
#     decrypted = f.decrypt(encrypted)
#     assert encoded == decrypted



