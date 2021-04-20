import codecs
import pickle
from .secure import create_key, load_key
from cryptography.fernet import Fernet

create_key()
key = load_key()
f = Fernet(key)

def pickleToString(obj):
    pickled = codecs.encode(f.encrypt(pickle.dumps(obj)), "base64").decode()
    return pickled

def unpickleFromString(pickled):
    unpickled = pickle.loads(f.decrypt(codecs.decode(pickled.encode(), "base64")))
    return unpickled

