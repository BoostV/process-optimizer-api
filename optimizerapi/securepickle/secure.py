from cryptography.fernet import Fernet

def is_initialized():
    pass

def load_key():
    with open('mykey.key', 'rb') as mykey:
        key = mykey.read()
    return key

def create_key():
    key = Fernet.generate_key()
    with open('mykey.key', 'wb') as mykey:
        mykey.write(key)