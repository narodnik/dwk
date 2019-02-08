import ecdsa
import os
from darkwiki.ecdsa.ecc import ECPubkey, ECPrivkey

def random_secret():
    return os.urandom(32)

def encrypt(message, public):
    public_key = ECPubkey(public)
    return public_key.encrypt_message(message)

def decrypt(cipher, secret):
    private = ECPrivkey(secret)
    return private.decrypt_message(cipher)

def sign(message, secret):
    private = ECPrivkey(secret)
    return private.sign(message)

def verify(signature, message, public):
    public_key = ECPubkey(public)
    try:
        public_key.verify_message_hash(signature, message)
    except:
        return False
    return True

def secret_to_public(secret):
    private = ECPrivkey(secret)
    return private.get_public_key_bytes()

