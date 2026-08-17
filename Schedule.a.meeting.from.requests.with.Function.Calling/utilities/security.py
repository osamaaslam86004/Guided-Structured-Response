import os
import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

# Master key loaded from environment variable
MASTER_KEY_HEX = os.getenv("APP_MASTER_KEY")
if not MASTER_KEY_HEX:
    # Example generation: bytes.fromhex(AESGCM.generate_key(bit_length=256).hex())
    raise RuntimeError("APP_MASTER_KEY environment variable is required!")

MASTER_KEY = bytes.fromhex(MASTER_KEY_HEX)


def _get_kek(salt: bytes) -> AESGCM:
    """Derive a KEK from the Master Key using HKDF."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"envelope-encryption-kek",
    )
    return AESGCM(hkdf.derive(MASTER_KEY))


def encrypt_envelope(plaintext: str) -> str:
    """
    Encrypts data using a unique Data Encryption Key (DEK).
    The DEK is encrypted using a derived Key Encryption Key (KEK).
    """
    if plaintext is None:
        return None

    # 1. Generate unique DEK and KEK derivation salt
    kek_salt = os.urandom(16)
    dek_raw = AESGCM.generate_key(bit_length=256)
    
    # 2. Encrypt plaintext using DEK
    dek_cipher = AESGCM(dek_raw)
    data_nonce = os.urandom(12)
    ciphertext = dek_cipher.encrypt(data_nonce, plaintext.encode("utf-8"), None)

    # 3. Encrypt DEK using derived KEK
    kek_cipher = _get_kek(kek_salt)
    dek_nonce = os.urandom(12)
    encrypted_dek = kek_cipher.encrypt(dek_nonce, dek_raw, None)

    # 4. Package into payload
    payload = {
        "kek_salt": base64.b64encode(kek_salt).decode("utf-8"),
        "dek_nonce": base64.b64encode(dek_nonce).decode("utf-8"),
        "encrypted_dek": base64.b64encode(encrypted_dek).decode("utf-8"),
        "data_nonce": base64.b64encode(data_nonce).decode("utf-8"),
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
    }
    return json.dumps(payload)


def decrypt_envelope(payload_json: str) -> str:
    """Decrypts an envelope payload back into plaintext."""
    if payload_json is None:
        return None

    payload = json.loads(payload_json)

    kek_salt = base64.b64decode(payload["kek_salt"])
    dek_nonce = base64.b64decode(payload["dek_nonce"])
    encrypted_dek = base64.b64decode(payload["encrypted_dek"])
    data_nonce = base64.b64decode(payload["data_nonce"])
    ciphertext = base64.b64decode(payload["ciphertext"])

    # 1. Reconstruct KEK and decrypt DEK
    kek_cipher = _get_kek(kek_salt)
    dek_raw = kek_cipher.decrypt(dek_nonce, encrypted_dek, None)

    # 2. Decrypt ciphertext using DEK
    dek_cipher = AESGCM(dek_raw)
    plaintext_bytes = dek_cipher.decrypt(data_nonce, ciphertext, None)

    return plaintext_bytes.decode("utf-8")