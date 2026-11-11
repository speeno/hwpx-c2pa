"""Create a throw-away certificate hierarchy for trying hwpx-c2pa.

FOR TESTING ONLY. Real signing needs a certificate from a CA on the C2PA trust
list or from your organisation's PKI. Requires the ``cryptography`` package
(``pip install hwpx-c2pa[devcerts]``).

Files written:
  root-ca.pem      trust anchor (use with ``verify --trust``)
  signer-chain.pem leaf certificate followed by the intermediate CA
  signer.key       PKCS#8 private key of the leaf (P-256, for es256)
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path


def create(outdir: str | Path, common_name: str = "hwpx-c2pa test signer",
           days: int = 365) -> dict[str, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID, ObjectIdentifier

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)

    def name(cn: str) -> x509.Name:
        return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn),
                          x509.NameAttribute(NameOID.ORGANIZATION_NAME, "hwpx-c2pa test only")])

    def build(subject, issuer, pub, issuer_key, *, ca: bool, path_len=None, eku=None, issuer_pub=None):
        b = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
             .public_key(pub).serial_number(x509.random_serial_number())
             .not_valid_before(now).not_valid_after(now + dt.timedelta(days=days))
             .add_extension(x509.BasicConstraints(ca=ca, path_length=path_len), critical=True)
             .add_extension(x509.SubjectKeyIdentifier.from_public_key(pub), critical=False)
             .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_pub or pub),
                            critical=False))
        if ca:
            b = b.add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                              content_commitment=False, key_encipherment=False,
                                              data_encipherment=False, key_agreement=False,
                                              encipher_only=False, decipher_only=False), critical=True)
        else:
            b = b.add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=False, crl_sign=False,
                                              content_commitment=False, key_encipherment=False,
                                              data_encipherment=False, key_agreement=False,
                                              encipher_only=False, decipher_only=False), critical=True)
            b = b.add_extension(x509.ExtendedKeyUsage(eku), critical=False)
        return b.sign(issuer_key, hashes.SHA256())

    root_key = ec.generate_private_key(ec.SECP256R1())
    root = build(name("hwpx-c2pa test root CA"), name("hwpx-c2pa test root CA"),
                 root_key.public_key(), root_key, ca=True, path_len=1)
    int_key = ec.generate_private_key(ec.SECP256R1())
    inter = build(name("hwpx-c2pa test intermediate CA"), root.subject, int_key.public_key(),
                  root_key, ca=True, path_len=0, issuer_pub=root_key.public_key())
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    document_signing = ObjectIdentifier("1.3.6.1.5.5.7.3.36")
    leaf = build(name(common_name), inter.subject, leaf_key.public_key(), int_key, ca=False,
                 eku=[ExtendedKeyUsageOID.EMAIL_PROTECTION, document_signing],
                 issuer_pub=int_key.public_key())

    pem = serialization.Encoding.PEM
    paths = {"root": out / "root-ca.pem", "chain": out / "signer-chain.pem", "key": out / "signer.key"}
    paths["root"].write_bytes(root.public_bytes(pem))
    paths["chain"].write_bytes(leaf.public_bytes(pem) + inter.public_bytes(pem))
    paths["key"].write_bytes(leaf_key.private_bytes(pem, serialization.PrivateFormat.PKCS8,
                                                    serialization.NoEncryption()))
    return paths
