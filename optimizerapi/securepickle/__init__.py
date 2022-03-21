"""
Module that provides support for encrypted pickle functionality
"""
from .pickler import pickleToString, unpickleFromString
from .secure import get_crypto
