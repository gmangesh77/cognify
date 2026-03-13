import bcrypt

_COST_FACTOR = 12


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=_COST_FACTOR)
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
