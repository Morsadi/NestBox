# cert_utils.py
import os
import datetime
import ipaddress

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def ensure_self_signed_cert(ip_str: str, cert_path: str, key_path: str, days: int = 365) -> None:
    """
    Generate a self-signed certificate for the given IP if it doesn't exist yet.
    Uses cryptography, no external OpenSSL needed.
    """
    # If both files already exist, do nothing
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return

    os.makedirs(os.path.dirname(cert_path), exist_ok=True)

    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, ip_str),
        ]
    )

    # IP for SAN
    ip_obj = ipaddress.ip_address(ip_str)

    now = datetime.datetime.utcnow()

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=days))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ip_obj)]),
            critical=False,
        )
        .sign(private_key=key, algorithm=hashes.SHA256())
    )

    # Write key
    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Write cert
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
