from cryptography.fernet import Fernet
import os


def get_crypto(key=None):
    if key == None:
        key = os.getenv("PICKLE_KEY", None)
    if key == None:
        print("No key found, generating new key")
        key = Fernet.generate_key()
        os.environ["PICKLE_KEY"] = key.decode("utf-8")
        print("To reuse key for future server runs, set environment variable PICKLE_KEY=" +
              os.environ["PICKLE_KEY"])
    return Fernet(key)
