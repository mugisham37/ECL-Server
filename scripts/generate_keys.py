#!/usr/bin/env python3
"""Generate RSA-2048 key pair for JWT signing."""

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_b64 = base64.b64encode(private_pem).decode()
    public_b64 = base64.b64encode(public_pem).decode()
    print("Add to .env:")
    print(f"JWT_PRIVATE_KEY={private_b64}")
    print(f"JWT_PUBLIC_KEY={public_b64}")
    keys_dir = Path(__file__).resolve().parent.parent / "keys"
    keys_dir.mkdir(exist_ok=True)
    (keys_dir / "private.pem").write_bytes(private_pem)
    (keys_dir / "public.pem").write_bytes(public_pem)
    print(f"PEM files written to {keys_dir}/")


if __name__ == "__main__":
    main()
