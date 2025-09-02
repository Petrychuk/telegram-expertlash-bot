import secrets

secret = secrets.token_hex(32)
print("Ваш JWT_SECRET:\n")
print(secret)