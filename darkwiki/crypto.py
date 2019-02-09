import nacl
from nacl.public import PrivateKey, PublicKey, Box

def random_secret():
    private = PrivateKey.generate()
    return bytes(private)

def secret_to_public(secret):
    private = PrivateKey(secret)
    return bytes(private.public_key)

def encrypt_sign(message, secret_origin, public_destination):
    public = PublicKey(public_destination)
    private = PrivateKey(secret_origin)
    box = Box(private, public)
    return box.encrypt(message)

def decrypt_verify(cipher, public_origin, private_destination):
    public = PublicKey(public_origin)
    private = PrivateKey(private_destination)
    box = Box(private, public)
    try:
        return box.decrypt(cipher)
    except nacl.exceptions.CryptoError:
        return None

if __name__ == '__main__':
    secret = random_secret()
    public = secret_to_public(secret)
    print(len(secret), len(public))

    message = b'helssdkjsd skslo mdhjdhjsdksddskddsjdkjjk' * 10
    cipher = encrypt_sign(message, secret, public)
    message_2 = decrypt_verify(cipher, public, secret)
    assert type(message_2) == bytes
    assert message == message_2

