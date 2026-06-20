"""Generate AFIP WSAA CSR and private key for this desktop app.

AFIP expects a `cert.crt` signed for the same key used to generate the CSR.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def generate_key_and_csr(cuit: str, output_dir: Path) -> tuple[Path, Path]:
    """Generate `private.key` and `solicitud.csr` using OpenSSL."""
    cuit_clean = cuit.strip().replace("-", "")
    if not cuit_clean.isdigit():
        raise ValueError("CUIT inválido (esperado numérico, con o sin guiones).")

    output_dir.mkdir(parents=True, exist_ok=True)

    key_path = output_dir / "private.key"
    csr_path = output_dir / "solicitud.csr"

    subject = f"/CN={int(cuit_clean)}"
    cmd = [
        "openssl",
        "req",
        "-new",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        str(key_path),
        "-out",
        str(csr_path),
        "-subj",
        subject,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"OpenSSL CSR generation failed: {result.stderr}")

    return key_path, csr_path

