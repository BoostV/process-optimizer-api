import codecs
import pickle


def pickleToString(obj, crypto):
    pickled = codecs.encode(crypto.encrypt(
        pickle.dumps(obj)), "base64").decode()
    return pickled


def unpickleFromString(pickled, crypto):
    unpickled = pickle.loads(crypto.decrypt(
        codecs.decode(pickled.encode(), "base64")))
    return unpickled
