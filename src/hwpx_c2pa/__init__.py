"""hwpx-c2pa: C2PA Content Credentials for HWPX (OWPML, KS X 6101) documents.

Copyright (c) 2026 Dongsun Nam (speeno). MIT License.

The engine is imported lazily, so that ``hwpx-c2pa fetch-lib`` can run before
the C2PA SDK chooses its native library.
"""
__version__ = "0.1.0"

_ENGINE_NAMES = {"NoManifest", "VerifyResult", "has_valid_binding", "independent_check",
                 "load_signer", "sign", "sign_file", "verify"}


def __getattr__(name):
    if name in _ENGINE_NAMES:
        from . import engine
        return getattr(engine, name)
    raise AttributeError(name)


__all__ = ["__version__", *sorted(_ENGINE_NAMES)]
