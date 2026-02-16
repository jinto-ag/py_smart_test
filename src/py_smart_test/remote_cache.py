"""Remote caching support for sharing AST cache across team/CI.

This module provides pluggable remote cache backends for sharing cached data
across multiple machines, enabling faster CI runs and team-wide cache sharing.

Supported backends:
- HTTP: Simple REST API backend
- S3: AWS S3 or S3-compatible storage
- Redis: Redis key-value store
- File: Network file share (NFS, SMB, etc.)
"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class RemoteCacheBackend(ABC):
    """Abstract base class for remote cache backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from remote cache.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found
        """
        pass

    @abstractmethod
    def set(self, key: str, data: Dict[str, Any]) -> bool:
        """Store data to remote cache.

        Args:
            key: Cache key
            data: Data to cache

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete data from remote cache.

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists in remote cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        pass


class FileShareBackend(RemoteCacheBackend):
    """Network file share backend (NFS, SMB, etc.)."""

    def __init__(self, base_path: str):
        """Initialize file share backend.

        Args:
            base_path: Base directory path for cache storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, key: str) -> Path:
        """Get file path for cache key."""
        # Use hash to avoid filesystem issues with special characters
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.base_path / f"{key_hash}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from file share."""
        file_path = self._get_file_path(key)
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read from file share: {e}")
            return None

    def set(self, key: str, data: Dict[str, Any]) -> bool:
        """Store data to file share."""
        file_path = self._get_file_path(key)
        try:
            with open(file_path, "w") as f:
                json.dump(data, f)
            return True
        except Exception as e:
            logger.error(f"Failed to write to file share: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete data from file share."""
        file_path = self._get_file_path(key)
        try:
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to delete from file share: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in file share."""
        return self._get_file_path(key).exists()


class HTTPBackend(RemoteCacheBackend):
    """HTTP REST API backend."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """Initialize HTTP backend.

        Args:
            base_url: Base URL for cache API
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        try:
            import requests  # type: ignore[import-untyped]

            self.requests = requests
            self.has_requests = True
        except ImportError:
            logger.warning("requests library not found, HTTP backend disabled")
            self.has_requests = False

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from HTTP cache."""
        if not self.has_requests:
            return None

        try:
            response = self.requests.get(
                f"{self.base_url}/cache/{key}",
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.warning(f"Failed to get from HTTP cache: {e}")
            return None

    def set(self, key: str, data: Dict[str, Any]) -> bool:
        """Store data to HTTP cache."""
        if not self.has_requests:
            return False

        try:
            response = self.requests.put(
                f"{self.base_url}/cache/{key}",
                json=data,
                headers=self._get_headers(),
                timeout=10,
            )
            return response.status_code in (200, 201)
        except Exception as e:
            logger.error(f"Failed to set HTTP cache: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete data from HTTP cache."""
        if not self.has_requests:
            return False

        try:
            response = self.requests.delete(
                f"{self.base_url}/cache/{key}",
                headers=self._get_headers(),
                timeout=5,
            )
            return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Failed to delete from HTTP cache: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in HTTP cache."""
        if not self.has_requests:
            return False

        try:
            response = self.requests.head(
                f"{self.base_url}/cache/{key}",
                headers=self._get_headers(),
                timeout=5,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to check HTTP cache: {e}")
            return False


class RedisBackend(RemoteCacheBackend):
    """Redis key-value store backend."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = "py_smart_test:",
    ):
        """Initialize Redis backend.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Optional Redis password
            prefix: Key prefix to namespace cache entries
        """
        self.prefix = prefix

        try:
            import redis  # type: ignore[import-untyped]

            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=False,
            )
            self.has_redis = True
        except ImportError:
            logger.warning("redis library not found, Redis backend disabled")
            self.has_redis = False

    def _make_key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self.prefix}{key}"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from Redis."""
        if not self.has_redis:
            return None

        try:
            data = self.redis_client.get(self._make_key(key))
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"Failed to get from Redis: {e}")
            return None

    def set(self, key: str, data: Dict[str, Any]) -> bool:
        """Store data to Redis."""
        if not self.has_redis:
            return False

        try:
            json_data = json.dumps(data)
            self.redis_client.set(self._make_key(key), json_data)
            return True
        except Exception as e:
            logger.error(f"Failed to set Redis cache: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete data from Redis."""
        if not self.has_redis:
            return False

        try:
            self.redis_client.delete(self._make_key(key))
            return True
        except Exception as e:
            logger.error(f"Failed to delete from Redis: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self.has_redis:
            return False

        try:
            return bool(self.redis_client.exists(self._make_key(key)))
        except Exception as e:
            logger.warning(f"Failed to check Redis: {e}")
            return False


class S3Backend(RemoteCacheBackend):
    """AWS S3 or S3-compatible storage backend."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "py_smart_test/",
        region: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        """Initialize S3 backend.

        Args:
            bucket: S3 bucket name
            prefix: Key prefix within bucket
            region: AWS region (optional)
            endpoint_url: Custom endpoint URL for S3-compatible storage
        """
        self.bucket = bucket
        self.prefix = prefix

        try:
            import boto3

            self.s3_client = boto3.client(
                "s3",
                region_name=region,
                endpoint_url=endpoint_url,
            )
            self.has_boto3 = True
        except ImportError:
            logger.warning("boto3 library not found, S3 backend disabled")
            self.has_boto3 = False

    def _make_key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self.prefix}{key}"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from S3."""
        if not self.has_boto3:
            return None

        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=self._make_key(key),
            )
            data = response["Body"].read()
            return json.loads(data)
        except self.s3_client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            logger.warning(f"Failed to get from S3: {e}")
            return None

    def set(self, key: str, data: Dict[str, Any]) -> bool:
        """Store data to S3."""
        if not self.has_boto3:
            return False

        try:
            json_data = json.dumps(data)
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=self._make_key(key),
                Body=json_data.encode(),
                ContentType="application/json",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to set S3 cache: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete data from S3."""
        if not self.has_boto3:
            return False

        try:
            self.s3_client.delete_object(
                Bucket=self.bucket,
                Key=self._make_key(key),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete from S3: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in S3."""
        if not self.has_boto3:
            return False

        try:
            self.s3_client.head_object(
                Bucket=self.bucket,
                Key=self._make_key(key),
            )
            return True
        except self.s3_client.exceptions.ClientError:
            return False
        except Exception as e:
            logger.warning(f"Failed to check S3: {e}")
            return False


def create_backend(url: str) -> Optional[RemoteCacheBackend]:
    """Create remote cache backend from URL.

    Supported URL schemes:
    - file:///path/to/share - Network file share
    - http://host:port or https://host:port - HTTP REST API
    - redis://host:port/db - Redis
    - s3://bucket/prefix - AWS S3

    Args:
        url: Remote cache URL

    Returns:
        Backend instance or None if URL is invalid
    """
    parsed = urlparse(url)

    if parsed.scheme in ("file", ""):
        path = parsed.path or parsed.netloc
        return FileShareBackend(path)

    elif parsed.scheme in ("http", "https"):
        return HTTPBackend(url)

    elif parsed.scheme == "redis":
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        db = int(parsed.path.lstrip("/")) if parsed.path else 0
        password = parsed.password
        return RedisBackend(host, port, db, password)

    elif parsed.scheme == "s3":
        bucket = parsed.netloc
        prefix = parsed.path.lstrip("/")
        return S3Backend(bucket, prefix)

    else:
        logger.error(f"Unsupported remote cache scheme: {parsed.scheme}")
        return None


def get_remote_cache_url() -> Optional[str]:
    """Get remote cache URL from environment.

    Checks the following environment variables:
    - PY_SMART_TEST_REMOTE_CACHE
    - REMOTE_CACHE_URL

    Returns:
        Remote cache URL or None if not configured
    """
    import os

    return os.environ.get("PY_SMART_TEST_REMOTE_CACHE") or os.environ.get(
        "REMOTE_CACHE_URL"
    )


def get_remote_cache_backend() -> Optional[RemoteCacheBackend]:
    """Get configured remote cache backend.

    Returns:
        Backend instance or None if remote caching is not configured
    """
    url = get_remote_cache_url()
    if not url:
        return None

    backend = create_backend(url)
    if backend:
        logger.info(f"Using remote cache: {url}")
    return backend
