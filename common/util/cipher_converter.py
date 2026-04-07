from loguru import logger


class CipherConverter:
    IANA_TO_OPENSSL = {
        'TLS_AES_256_GCM_SHA384': 'TLS_AES_256_GCM_SHA384',
        'TLS_AES_128_GCM_SHA256': 'TLS_AES_128_GCM_SHA256',
        'TLS_CHACHA20_POLY1305_SHA256': 'TLS_CHACHA20_POLY1305_SHA256',

        'TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384': 'ECDHE-ECDSA-AES256-GCM-SHA384',
        'TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256': 'ECDHE-ECDSA-AES128-GCM-SHA256',

        'TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384': 'ECDHE-RSA-AES256-GCM-SHA384',
        'TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256': 'ECDHE-RSA-AES128-GCM-SHA256',

        'TLS_DHE_RSA_WITH_AES_256_GCM_SHA384': 'DHE-RSA-AES256-GCM-SHA384',
        'TLS_DHE_RSA_WITH_AES_128_GCM_SHA256': 'DHE-RSA-AES128-GCM-SHA256',

        'TLS_DHE_DSS_WITH_AES_256_GCM_SHA384': 'DHE-DSS-AES256-GCM-SHA384',
        'TLS_DHE_DSS_WITH_AES_128_GCM_SHA256': 'DHE-DSS-AES128-GCM-SHA256',
    }

    @classmethod
    def convert(cls, iana_cipher_string) -> str:
        ciphers = [c.strip() for c in iana_cipher_string.split(',')]

        openssl_ciphers = []
        for cipher in ciphers:
            if cipher in cls.IANA_TO_OPENSSL:
                openssl_ciphers.append(cls.IANA_TO_OPENSSL[cipher])
            else:
                converted = cls._auto_convert(cipher)
                if converted:
                    openssl_ciphers.append(converted)
                    logger.info(f"Waring:auto convert {cipher} -> {converted}")
                else:
                    logger.info(f"Waring: skip unrecognized cipher: {cipher}")
        return ':'.join(openssl_ciphers)

    @classmethod
    def _auto_convert(cls, cipher) -> str:
        try:
            if cipher.startswith('TLS_'):
                cipher = cipher[len('TLS_'):]
            cipher = cipher.replace('_WITH_', '-')
            cipher = cipher.replace('_', '-')
            return cipher
        except Exception as e:
            logger.error(f"Convert Cipher Failed: {e}")
            return ""
