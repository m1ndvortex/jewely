"""
Encryption and compression utilities for the backup system.

This module provides utilities for:
1. AES-256 encryption using Fernet (symmetric encryption)
2. Gzip compression with level 9 (maximum compression)
3. SHA-256 checksum calculation
4. Backup verification across all storage locations

All backups are compressed first, then encrypted, following the pattern:
Original File -> Gzip Compression -> AES-256 Encryption -> Storage
"""

import gzip
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple

from django.conf import settings

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption operations fail."""

    pass


class CompressionError(Exception):
    """Raised when compression operations fail."""

    pass


class ChecksumError(Exception):
    """Raised when checksum verification fails."""

    pass


def get_encryption_key() -> bytes:
    """
    Get the encryption key from Django settings.

    The key should be a 32-byte URL-safe base64-encoded key.
    Generate a new key with: Fernet.generate_key()

    Returns:
        Encryption key as bytes

    Raises:
        ValueError: If encryption key is not configured
    """
    key = getattr(settings, "BACKUP_ENCRYPTION_KEY", None)

    if not key:
        raise ValueError(
            "BACKUP_ENCRYPTION_KEY not configured in settings. "
            "Generate a key with: from cryptography.fernet import Fernet; Fernet.generate_key()"
        )

    # Convert string to bytes if necessary
    if isinstance(key, str):
        key = key.encode("utf-8")

    return key


def compress_file(input_path: str, output_path: Optional[str] = None) -> Tuple[str, int, int]:
    """
    Compress a file using gzip with maximum compression (level 9).

    Args:
        input_path: Path to the file to compress
        output_path: Path for the compressed file (defaults to input_path + '.gz')

    Returns:
        Tuple of (output_path, original_size, compressed_size)

    Raises:
        CompressionError: If compression fails
        FileNotFoundError: If input file doesn't exist
    """
    try:
        input_file = Path(input_path)

        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Default output path
        if output_path is None:
            output_path = f"{input_path}.gz"

        output_file = Path(output_path)

        # Get original file size
        original_size = input_file.stat().st_size

        # Compress with maximum compression level (9)
        with open(input_file, "rb") as f_in:
            with gzip.open(output_file, "wb", compresslevel=9) as f_out:
                # Read and write in chunks to handle large files
                chunk_size = 1024 * 1024  # 1MB chunks
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

        # Get compressed file size
        compressed_size = output_file.stat().st_size

        # Calculate compression ratio
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

        logger.info(
            f"Compressed {input_path} -> {output_path}: "
            f"{original_size} bytes -> {compressed_size} bytes "
            f"({compression_ratio:.1f}% reduction)"
        )

        return str(output_path), original_size, compressed_size

    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to compress {input_path}: {e}")
        raise CompressionError(f"Compression failed: {e}") from e


def decompress_file(input_path: str, output_path: Optional[str] = None) -> str:
    """
    Decompress a gzip-compressed file.

    Args:
        input_path: Path to the compressed file
        output_path: Path for the decompressed file (defaults to input_path without .gz)

    Returns:
        Path to the decompressed file

    Raises:
        CompressionError: If decompression fails
        FileNotFoundError: If input file doesn't exist
    """
    try:
        input_file = Path(input_path)

        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Default output path (remove .gz extension)
        if output_path is None:
            if input_path.endswith(".gz"):
                output_path = input_path[:-3]
            else:
                output_path = f"{input_path}.decompressed"

        output_file = Path(output_path)

        # Decompress
        with gzip.open(input_file, "rb") as f_in:
            with open(output_file, "wb") as f_out:
                # Read and write in chunks to handle large files
                chunk_size = 1024 * 1024  # 1MB chunks
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

        logger.info(f"Decompressed {input_path} -> {output_path}")

        return str(output_path)

    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to decompress {input_path}: {e}")
        raise CompressionError(f"Decompression failed: {e}") from e


def encrypt_file(input_path: str, output_path: Optional[str] = None) -> str:
    """
    Encrypt a file using AES-256 (Fernet).

    Fernet uses AES-256 in CBC mode with HMAC-SHA256 for authentication.
    This provides both confidentiality and integrity protection.

    Args:
        input_path: Path to the file to encrypt
        output_path: Path for the encrypted file (defaults to input_path + '.enc')

    Returns:
        Path to the encrypted file

    Raises:
        EncryptionError: If encryption fails
        FileNotFoundError: If input file doesn't exist
    """
    try:
        input_file = Path(input_path)

        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Default output path
        if output_path is None:
            output_path = f"{input_path}.enc"

        output_file = Path(output_path)

        # Get encryption key
        key = get_encryption_key()
        fernet = Fernet(key)

        # Read, encrypt, and write
        with open(input_file, "rb") as f_in:
            plaintext = f_in.read()

        ciphertext = fernet.encrypt(plaintext)

        with open(output_file, "wb") as f_out:
            f_out.write(ciphertext)

        logger.info(f"Encrypted {input_path} -> {output_path}")

        return str(output_path)

    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to encrypt {input_path}: {e}")
        raise EncryptionError(f"Encryption failed: {e}") from e


def decrypt_file(input_path: str, output_path: Optional[str] = None) -> str:
    """
    Decrypt a file encrypted with AES-256 (Fernet).

    Args:
        input_path: Path to the encrypted file
        output_path: Path for the decrypted file (defaults to input_path without .enc)

    Returns:
        Path to the decrypted file

    Raises:
        EncryptionError: If decryption fails
        FileNotFoundError: If input file doesn't exist
    """
    try:
        input_file = Path(input_path)

        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Default output path (remove .enc extension)
        if output_path is None:
            if input_path.endswith(".enc"):
                output_path = input_path[:-4]
            else:
                output_path = f"{input_path}.decrypted"

        output_file = Path(output_path)

        # Get encryption key
        key = get_encryption_key()
        fernet = Fernet(key)

        # Read, decrypt, and write
        with open(input_file, "rb") as f_in:
            ciphertext = f_in.read()

        try:
            plaintext = fernet.decrypt(ciphertext)
        except InvalidToken:
            raise EncryptionError("Invalid encryption key or corrupted file")

        with open(output_file, "wb") as f_out:
            f_out.write(plaintext)

        logger.info(f"Decrypted {input_path} -> {output_path}")

        return str(output_path)

    except FileNotFoundError:
        raise
    except EncryptionError:
        raise
    except Exception as e:
        logger.error(f"Failed to decrypt {input_path}: {e}")
        raise EncryptionError(f"Decryption failed: {e}") from e


def calculate_checksum(file_path: str, algorithm: str = "sha256") -> str:  # noqa: C901
    """
    Calculate the checksum of a file.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use ('sha256', 'sha512', 'md5')

    Returns:
        Hexadecimal checksum string

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If algorithm is not supported
    """
    try:
        file = Path(file_path)

        if not file.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get hash algorithm
        if algorithm == "sha256":
            hasher = hashlib.sha256()
        elif algorithm == "sha512":
            hasher = hashlib.sha512()
        elif algorithm == "md5":
            hasher = hashlib.md5()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

        # Calculate hash in chunks to handle large files
        chunk_size = 1024 * 1024  # 1MB chunks
        with open(file, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)

        checksum = hasher.hexdigest()

        logger.debug(f"Calculated {algorithm} checksum for {file_path}: {checksum}")

        return checksum

    except FileNotFoundError:
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to calculate checksum for {file_path}: {e}")
        raise


def verify_checksum(file_path: str, expected_checksum: str, algorithm: str = "sha256") -> bool:
    """
    Verify the checksum of a file.

    Args:
        file_path: Path to the file
        expected_checksum: Expected checksum value
        algorithm: Hash algorithm to use ('sha256', 'sha512', 'md5')

    Returns:
        True if checksum matches, False otherwise

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    try:
        actual_checksum = calculate_checksum(file_path, algorithm)
        matches = actual_checksum.lower() == expected_checksum.lower()

        if matches:
            logger.info(f"Checksum verified for {file_path}")
        else:
            logger.warning(
                f"Checksum mismatch for {file_path}: "
                f"expected {expected_checksum}, got {actual_checksum}"
            )

        return matches

    except Exception as e:
        logger.error(f"Failed to verify checksum for {file_path}: {e}")
        return False


def compress_and_encrypt_file(
    input_path: str, output_path: Optional[str] = None, keep_intermediate: bool = False
) -> Tuple[str, str, int, int]:
    """
    Compress and encrypt a file in one operation.

    This is the recommended way to prepare backups for storage.
    The file is first compressed with gzip level 9, then encrypted with AES-256.

    Args:
        input_path: Path to the file to process
        output_path: Path for the final encrypted file (defaults to input_path + '.gz.enc')
        keep_intermediate: If True, keep the intermediate compressed file

    Returns:
        Tuple of (final_path, checksum, original_size, compressed_size, final_size)

    Raises:
        CompressionError: If compression fails
        EncryptionError: If encryption fails
        FileNotFoundError: If input file doesn't exist
    """
    try:
        # Default output path
        if output_path is None:
            output_path = f"{input_path}.gz.enc"

        # Step 1: Compress
        compressed_path, original_size, compressed_size = compress_file(input_path)

        # Step 2: Encrypt
        encrypted_path = encrypt_file(compressed_path, output_path)

        # Step 3: Calculate checksum of final encrypted file
        checksum = calculate_checksum(encrypted_path)

        # Get final file size
        final_size = Path(encrypted_path).stat().st_size

        # Clean up intermediate file if requested
        if not keep_intermediate:
            Path(compressed_path).unlink()
            logger.debug(f"Removed intermediate compressed file: {compressed_path}")

        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        logger.info(
            f"Compressed and encrypted {input_path} -> {encrypted_path}: "
            f"{original_size} bytes -> {compressed_size} bytes (compression: {compression_ratio:.1f}%) "
            f"-> {final_size} bytes (after encryption) "
            f"(checksum: {checksum[:16]}...)")

        return encrypted_path, checksum, original_size, compressed_size, final_size

    except (CompressionError, EncryptionError, FileNotFoundError):
        raise
    except Exception as e:
        logger.error(f"Failed to compress and encrypt {input_path}: {e}")
        raise


def decrypt_and_decompress_file(
    input_path: str, output_path: Optional[str] = None, keep_intermediate: bool = False
) -> str:
    """
    Decrypt and decompress a file in one operation.

    This reverses the compress_and_encrypt_file operation.
    The file is first decrypted, then decompressed.

    Args:
        input_path: Path to the encrypted file
        output_path: Path for the final decompressed file
        keep_intermediate: If True, keep the intermediate decrypted file

    Returns:
        Path to the final decompressed file

    Raises:
        EncryptionError: If decryption fails
        CompressionError: If decompression fails
        FileNotFoundError: If input file doesn't exist
    """
    try:
        # Step 1: Decrypt
        decrypted_path = decrypt_file(input_path)

        # Step 2: Decompress
        decompressed_path = decompress_file(decrypted_path, output_path)

        # Clean up intermediate file if requested
        if not keep_intermediate:
            Path(decrypted_path).unlink()
            logger.debug(f"Removed intermediate decrypted file: {decrypted_path}")

        logger.info(f"Decrypted and decompressed {input_path} -> {decompressed_path}")

        return decompressed_path

    except (EncryptionError, CompressionError, FileNotFoundError):
        raise
    except Exception as e:
        logger.error(f"Failed to decrypt and decompress {input_path}: {e}")
        raise


def verify_backup_integrity(  # noqa: C901
    file_path: str, expected_checksum: str, storage_backends: Optional[list] = None
) -> dict:
    """
    Verify backup integrity across all storage locations.

    This function checks:
    1. File exists in all specified storage locations
    2. Checksum matches the expected value in all locations
    3. File sizes are consistent across all locations

    Args:
        file_path: Relative path to the backup file
        expected_checksum: Expected SHA-256 checksum
        storage_backends: List of storage backend instances to check
                         (defaults to ['local', 'r2', 'b2'])

    Returns:
        Dictionary with verification results:
        {
            'valid': bool,  # True if all checks pass
            'locations': {
                'local': {'exists': bool, 'checksum_valid': bool, 'size': int},
                'r2': {'exists': bool, 'checksum_valid': bool, 'size': int},
                'b2': {'exists': bool, 'checksum_valid': bool, 'size': int}
            },
            'errors': [list of error messages]
        }
    """
    import tempfile

    from .storage import get_storage_backend

    results = {"valid": True, "locations": {}, "errors": []}

    # Default to all three storage backends
    if storage_backends is None:
        storage_backends = ["local", "r2", "b2"]

    for backend_name in storage_backends:
        location_result = {"exists": False, "checksum_valid": False, "size": None}

        try:
            backend = get_storage_backend(backend_name)

            # Check if file exists
            if not backend.exists(file_path):
                location_result["exists"] = False
                results["errors"].append(f"File not found in {backend_name}: {file_path}")
                results["valid"] = False
            else:
                location_result["exists"] = True

                # Get file size
                size = backend.get_size(file_path)
                location_result["size"] = size

                # Download and verify checksum
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name

                try:
                    if backend.download(file_path, temp_path):
                        # Verify checksum
                        if verify_checksum(temp_path, expected_checksum):
                            location_result["checksum_valid"] = True
                        else:
                            results["errors"].append(
                                f"Checksum mismatch in {backend_name}: {file_path}"
                            )
                            results["valid"] = False
                    else:
                        results["errors"].append(
                            f"Failed to download from {backend_name}: {file_path}"
                        )
                        results["valid"] = False
                finally:
                    # Clean up temp file
                    Path(temp_path).unlink(missing_ok=True)

        except Exception as e:
            results["errors"].append(f"Error verifying {backend_name}: {e}")
            results["valid"] = False
            logger.error(f"Error verifying backup in {backend_name}: {e}")

        results["locations"][backend_name] = location_result

    # Check size consistency across locations
    sizes = [loc["size"] for loc in results["locations"].values() if loc["size"] is not None]
    if sizes and len(set(sizes)) > 1:
        results["errors"].append(f"Inconsistent file sizes across locations: {sizes}")
        results["valid"] = False

    if results["valid"]:
        logger.info(f"Backup integrity verified for {file_path} across all locations")
    else:
        logger.warning(
            f"Backup integrity check failed for {file_path}: {', '.join(results['errors'])}"
        )

    return results
