DEFAULT_ENCODING = 'UTF-8'


def decrypt(ciphertext: str) -> bytes:
    return ciphertext.encode(DEFAULT_ENCODING)
