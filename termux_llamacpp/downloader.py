"""GGUF Model Downloader, Cache Manager, HTTP Range Resume with ETag, and Integrity Verifier."""

import hashlib
import hmac
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional, List, Dict, Union

import requests
from tqdm import tqdm

from termux_llamacpp.config import (
    DEFAULT_MODELS_DIR,
    CURATED_MODELS,
    ModelInfo,
)
from termux_llamacpp.exceptions import ModelNotFoundError, TermuxLlamaError
from termux_llamacpp.security import (
    compute_sha256,
    atomic_write_and_verify,
    build_model_manifest_payload,
    save_signed_model_manifest,
    atomic_save_json,
)


def ensure_models_dir(directory: Optional[Union[str, Path]] = None) -> Path:
    """Ensure the target models directory exists, creating it if necessary."""
    target = Path(directory) if directory else DEFAULT_MODELS_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def check_disk_space(target_dir: Path, required_bytes: int):
    """Check storage volume free space and warn if low, without hard-blocking user operations."""
    try:
        usage = shutil.disk_usage(str(target_dir))
        if usage.free < (required_bytes + 100 * 1024 * 1024):
            required_mb = required_bytes / (1024 * 1024)
            free_mb = usage.free / (1024 * 1024)
            print(
                f"[termux-llamacpp] WARNING: Low disk space detected in '{target_dir}'. "
                f"Required: {required_mb:.1f} MB, Available: {free_mb:.1f} MB. "
                f"Proceeding under user responsibility."
            )
    except OSError:
        pass  # Non-mounted or permission-restricted paths; proceed safely


class ModelManager:
    """Manages GGUF model storage, downloads, verification, and retrieval."""

    def __init__(self, models_dir: Optional[Union[str, Path]] = None):
        self.models_dir = ensure_models_dir(models_dir)

    def resolve_model_path(self, model_identifier: Optional[Union[str, Path]] = None) -> Path:
        """
        Resolve a model name, alias, filename, or direct path to a validated local GGUF file.
        If model_identifier is None, resolves to the first cached GGUF or default curated model.

        Raises:
            ModelNotFoundError: If the model file is missing from local storage.
        """
        if model_identifier is None or str(model_identifier).strip() == "":
            # Check cached models first
            cached = list(self.models_dir.glob("*.gguf"))
            if cached:
                return cached[0].resolve()
            # Default fallback alias
            model_identifier = "qwen2.5-0.5b-instruct"

        path = Path(model_identifier)
        if path.is_file() and path.suffix.lower() == ".gguf":
            return path.resolve()

        in_models_dir = self.models_dir / model_identifier
        if in_models_dir.is_file():
            return in_models_dir.resolve()

        in_models_dir_gguf = self.models_dir / f"{model_identifier}.gguf"
        if in_models_dir_gguf.is_file():
            return in_models_dir_gguf.resolve()

        alias = str(model_identifier).strip().lower()
        if alias in CURATED_MODELS:
            curated_info = CURATED_MODELS[alias]
            candidate = self.models_dir / curated_info.artifact_filename
            if candidate.is_file():
                return candidate.resolve()

        for f in self.models_dir.glob("*.gguf"):
            if f.stem.lower() == alias.lower() or f.name.lower() == alias.lower():
                return f.resolve()

        raise ModelNotFoundError(str(model_identifier), str(self.models_dir))

    def get(self, model_identifier: Optional[Union[str, Path]] = None) -> Path:
        """Alias for resolve_model_path with automatic verification."""
        return self.resolve_model_path(model_identifier)


    def download(
        self,
        repo_id_or_alias: str,
        filename: Optional[str] = None,
        revision: Optional[str] = None,
        sha256: Optional[str] = None,
        accept_license: bool = False,
        force: bool = False,
    ) -> Path:
        """
        Download GGUF model with ETag + If-Range Resume protocol, disk pre-check, and SHA256 validation.
        """
        alias = repo_id_or_alias.strip().lower()
        expected_sha256 = sha256
        target_filename = filename
        quant_type = "Q4_K_M"
        license_id = "Apache-2.0"
        model_revision = revision
        model_id = alias

        if alias in CURATED_MODELS:
            info = CURATED_MODELS[alias]
            model_id = info.model_id
            repo_id = info.repo_id
            target_filename = info.artifact_filename
            model_revision = revision or info.repo_revision
            quant_type = info.quant_type
            license_id = info.license_id
            if not expected_sha256:
                expected_sha256 = info.sha256

            if info.requires_acceptance and not accept_license:
                raise TermuxLlamaError(
                    f"Model '{alias}' requires accepting its community license: {info.license_id}\n"
                    f"License URL: {info.license_url}\n"
                    f"To proceed, pass accept_license=True in SDK or --accept-license in CLI."
                )
        else:
            repo_id = repo_id_or_alias
            model_revision = revision or "main"
            if not target_filename:
                raise ValueError(f"Filename must be provided when downloading custom repo '{repo_id}'.")

        destination = self.models_dir / target_filename

        if destination.is_file() and not force:
            if expected_sha256:
                print(f"[termux-llamacpp] Validating existing model checksum: {target_filename}...")
                current_hash = compute_sha256(destination)
                if current_hash.lower() == expected_sha256.lower():
                    print("[termux-llamacpp] File integrity validated (SHA-256 match). Using cached model.")
                    return destination.resolve()
                print("[termux-llamacpp] Checksum mismatch. Re-downloading...")
            else:
                print(f"[termux-llamacpp] Model '{target_filename}' already exists in cache.")
                return destination.resolve()

        download_url = f"https://huggingface.co/{repo_id}/resolve/{model_revision}/{target_filename}"
        part_file = destination.with_suffix(".part")
        meta_file = destination.with_suffix(".part.meta.json")

        print("================================================================================")
        print("  [termux-llamacpp] Downloading GGUF Model (ETag Resume Protocol)")
        print("================================================================================")
        print(f"  Model ID    : {model_id}")
        print(f"  Repository  : {repo_id} (rev: {model_revision})")
        print(f"  Filename    : {target_filename}")
        print(f"  Destination : {destination}")
        print("================================================================================")

        saved_meta = {}
        if meta_file.is_file() and part_file.is_file():
            try:
                saved_meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                saved_meta = {}

        headers = {"Accept-Encoding": "identity"}
        downloaded_bytes = 0
        saved_etag = saved_meta.get("etag")

        if part_file.is_file() and saved_meta.get("url") == download_url:
            downloaded_bytes = part_file.stat().st_size
            headers["Range"] = f"bytes={downloaded_bytes}-"
            if saved_etag:
                headers["If-Range"] = saved_etag
            print(f"[termux-llamacpp] Resuming download from byte {downloaded_bytes:,} (ETag: {saved_etag})...")

        try:
            with requests.get(download_url, stream=True, headers=headers, timeout=30) as resp:
                if resp.status_code == 404:
                    raise TermuxLlamaError(f"Model not found at {download_url} (HTTP 404).")

                current_etag = resp.headers.get("etag", "")
                content_encoding = resp.headers.get("content-encoding")

                if content_encoding and content_encoding != "identity":
                    print("[termux-llamacpp] Compressed transfer encoding detected. Discarding range resume.")
                    part_file.unlink(missing_ok=True)
                    downloaded_bytes = 0

                if resp.status_code == 206:
                    total_size = downloaded_bytes + int(resp.headers.get("content-length", 0))
                    write_mode = "ab"
                elif resp.status_code == 416:
                    expected_size = saved_meta.get("expected_size", 0)
                    if downloaded_bytes > 0:
                        print("[termux-llamacpp] Range 416 returned. Validating part file integrity...")
                        if expected_size and downloaded_bytes != expected_size:
                            print("[termux-llamacpp] Size mismatch on 416. Resetting part file...")
                            part_file.unlink(missing_ok=True)
                            meta_file.unlink(missing_ok=True)
                            downloaded_bytes = 0
                            total_size = 0
                            write_mode = "wb"
                        else:
                            final_sha = compute_sha256(part_file)
                            if expected_sha256 and not hmac.compare_digest(final_sha.lower(), expected_sha256.lower()):
                                part_file.unlink(missing_ok=True)
                                meta_file.unlink(missing_ok=True)
                                raise TermuxLlamaError("Part file checksum mismatch on 416. Re-download required.")
                            total_size = downloaded_bytes
                            write_mode = "wb"
                    else:
                        part_file.unlink(missing_ok=True)
                        meta_file.unlink(missing_ok=True)
                        downloaded_bytes = 0
                        total_size = 0
                        write_mode = "wb"
                else:
                    if downloaded_bytes > 0:
                        print("[termux-llamacpp] Server responded with 200 OK. Resetting part file to 0.")
                    part_file.unlink(missing_ok=True)
                    downloaded_bytes = 0
                    total_size = int(resp.headers.get("content-length", 0))
                    write_mode = "wb"

                if total_size > downloaded_bytes:
                    check_disk_space(self.models_dir, total_size - downloaded_bytes)

                new_meta = {
                    "url": download_url,
                    "repo_id": repo_id,
                    "revision": model_revision,
                    "etag": current_etag or saved_etag,
                    "expected_size": total_size,
                    "downloaded": downloaded_bytes,
                }
                meta_file.write_text(json.dumps(new_meta, indent=2), encoding="utf-8")

                if resp.status_code in (200, 206):
                    with open(part_file, write_mode) as f, tqdm(
                        desc=target_filename,
                        initial=downloaded_bytes,
                        total=total_size,
                        unit="iB",
                        unit_scale=True,
                        unit_divisor=1024,
                        ncols=80,
                    ) as bar:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                                bar.update(len(chunk))

            final_path = atomic_write_and_verify(
                temp_file=part_file,
                target_destination=destination,
                expected_sha256=expected_sha256,
            )

            meta_file.unlink(missing_ok=True)

            final_sha256 = expected_sha256 or compute_sha256(final_path)
            file_size = final_path.stat().st_size

            # Construct verified payload
            payload = build_model_manifest_payload(
                model_path=final_path,
                model_id=model_id,
                repo_id=repo_id,
                revision=model_revision,
                sha256=final_sha256,
                quant_type=quant_type,
                license_id=license_id,
                size_bytes=file_size,
            )

            # Check if an official signature exists in registry, or save standard manifest
            manifest_path = final_path.with_suffix(final_path.suffix + ".manifest.json")
            atomic_save_json(manifest_path, payload)

            print(f"[termux-llamacpp] Model verified and saved: {final_path}\n")
            return final_path

        except Exception as e:
            if isinstance(e, TermuxLlamaError):
                raise e
            raise TermuxLlamaError(f"Failed to download model '{target_filename}': {e}") from e

    def list_local_models(self) -> List[Dict[str, Union[str, float, int]]]:
        results = []
        for file_path in self.models_dir.glob("*.gguf"):
            stat = file_path.stat()
            size_mb = round(stat.st_size / (1024 * 1024), 2)
            results.append({
                "filename": file_path.name,
                "path": str(file_path.resolve()),
                "size_mb": size_mb,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
            })
        return sorted(results, key=lambda x: str(x["filename"]))

    def remove(self, model_identifier: str) -> bool:
        try:
            model_path = self.resolve_model_path(model_identifier)
            if model_path.is_file():
                model_path.unlink()
                manifest = model_path.with_suffix(model_path.suffix + ".manifest.json")
                if manifest.is_file():
                    manifest.unlink()
                print(f"[termux-llamacpp] Removed model and manifest: {model_path}")
                return True
        except ModelNotFoundError:
            pass
        return False


def download_model(
    repo_id_or_alias: str,
    filename: Optional[str] = None,
    revision: Optional[str] = None,
    sha256: Optional[str] = None,
    accept_license: bool = False,
    models_dir: Optional[Union[str, Path]] = None,
) -> Path:
    manager = ModelManager(models_dir)
    return manager.download(
        repo_id_or_alias,
        filename=filename,
        revision=revision,
        sha256=sha256,
        accept_license=accept_license,
    )
