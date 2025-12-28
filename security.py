from cryptography.fernet import Fernet
import json
import os

KEY_FILE = 'secret.key'
CONFIG_FILE = 'config.json'

def load_key():
    """
    Loads the key from the current directory named `secret.key`
    """
    if os.path.exists(KEY_FILE):
        return open(KEY_FILE, "rb").read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as key_file:
            key_file.write(key)
        return key

def encrypt_data(data, key):
    """
    Encrypts data
    """
    f = Fernet(key)
    return f.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data, key):
    """
    Decrypts data
    """
    f = Fernet(key)
    return f.decrypt(encrypted_data.encode()).decode()

def save_encrypted_config(config):
    """
    Saves configuration to a file, encrypting sensitive fields.
    """
    key = load_key()
    json_str = json.dumps(config)
    encrypted_str = encrypt_data(json_str, key)

    with open(CONFIG_FILE, 'w') as f:
        json.dump({'data': encrypted_str}, f)

def load_encrypted_config():
    """
    Loads configuration from a file, decrypting it.
    """
    if not os.path.exists(CONFIG_FILE):
        return {}

    try:
        with open(CONFIG_FILE, 'r') as f:
            content = json.load(f)

        if 'data' in content:
            key = load_key()
            decrypted_str = decrypt_data(content['data'], key)
            return json.loads(decrypted_str)
        else:
            # Fallback for old unencrypted config
            # We should probably encrypt it immediately if we find it unencrypted,
            # but for now let's just return it.
            return content
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}
