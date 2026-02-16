"""Tests for remote caching functionality."""

import json
from unittest.mock import Mock, patch

from py_smart_test.remote_cache import (
    FileShareBackend,
    HTTPBackend,
    RedisBackend,
    S3Backend,
    create_backend,
    get_remote_cache_backend,
    get_remote_cache_url,
)


class TestFileShareBackend:
    """Tests for FileShareBackend."""

    def test_init(self, tmp_path):
        """Test initialization."""
        backend = FileShareBackend(str(tmp_path))
        assert backend.base_path == tmp_path
        assert tmp_path.exists()

    def test_set_and_get(self, tmp_path):
        """Test storing and retrieving data."""
        backend = FileShareBackend(str(tmp_path))
        test_data = {"test": "value", "number": 42}

        # Set data
        success = backend.set("test_key", test_data)
        assert success is True

        # Get data
        retrieved = backend.get("test_key")
        assert retrieved == test_data

    def test_get_nonexistent(self, tmp_path):
        """Test getting nonexistent key."""
        backend = FileShareBackend(str(tmp_path))
        result = backend.get("nonexistent")
        assert result is None

    def test_exists(self, tmp_path):
        """Test checking if key exists."""
        backend = FileShareBackend(str(tmp_path))

        assert backend.exists("missing") is False

        backend.set("present", {"data": "value"})
        assert backend.exists("present") is True

    def test_delete(self, tmp_path):
        """Test deleting data."""
        backend = FileShareBackend(str(tmp_path))

        backend.set("to_delete", {"data": "value"})
        assert backend.exists("to_delete") is True

        success = backend.delete("to_delete")
        assert success is True
        assert backend.exists("to_delete") is False

    def test_delete_nonexistent(self, tmp_path):
        """Test deleting nonexistent key."""
        backend = FileShareBackend(str(tmp_path))
        success = backend.delete("nonexistent")
        assert success is True  # Should not fail

    def test_set_handles_corrupt_data(self, tmp_path):
        """Test handling of errors during set."""
        backend = FileShareBackend(str(tmp_path))

        # Make directory read-only to cause write failure
        backend.base_path.chmod(0o444)

        try:
            success = backend.set("test", {"data": "value"})
            assert success is False
        finally:
            # Restore permissions
            backend.base_path.chmod(0o755)

    def test_get_handles_corrupt_file(self, tmp_path):
        """Test handling of corrupt cache files."""
        backend = FileShareBackend(str(tmp_path))

        # Write invalid JSON
        file_path = backend._get_file_path("corrupt")
        file_path.write_text("invalid json{{{")

        result = backend.get("corrupt")
        assert result is None


class TestHTTPBackend:
    """Tests for HTTPBackend."""

    def test_init(self):
        """Test initialization."""
        backend = HTTPBackend("http://cache.example.com", api_key="secret")
        assert backend.base_url == "http://cache.example.com"
        assert backend.api_key == "secret"

    def test_init_without_requests(self):
        """Test initialization when requests is not available."""
        backend = HTTPBackend("http://example.com")
        backend.has_requests = False
        backend.base_url = "http://example.com"

        result = backend.get("test")
        assert result is None

    def test_get_success(self):
        """Test successful GET request."""
        backend = HTTPBackend("http://cache.example.com")
        backend.has_requests = True

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}

        mock_requests = Mock()
        mock_requests.get.return_value = mock_response
        backend.requests = mock_requests

        result = backend.get("test_key")
        assert result == {"data": "value"}
        mock_requests.get.assert_called_once()

    def test_get_not_found(self):
        """Test GET request for nonexistent key."""
        backend = HTTPBackend("http://cache.example.com")
        backend.has_requests = True

        mock_response = Mock()
        mock_response.status_code = 404

        mock_requests = Mock()
        mock_requests.get.return_value = mock_response
        backend.requests = mock_requests

        result = backend.get("missing")
        assert result is None

    def test_set_success(self):
        """Test successful PUT request."""
        backend = HTTPBackend("http://cache.example.com")
        backend.has_requests = True

        mock_response = Mock()
        mock_response.status_code = 200

        mock_requests = Mock()
        mock_requests.put.return_value = mock_response
        backend.requests = mock_requests

        success = backend.set("test_key", {"data": "value"})
        assert success is True
        mock_requests.put.assert_called_once()

    def test_delete_success(self):
        """Test successful DELETE request."""
        backend = HTTPBackend("http://cache.example.com")
        backend.has_requests = True

        mock_response = Mock()
        mock_response.status_code = 204

        mock_requests = Mock()
        mock_requests.delete.return_value = mock_response
        backend.requests = mock_requests

        success = backend.delete("test_key")
        assert success is True

    def test_exists_true(self):
        """Test exists check for existing key."""
        backend = HTTPBackend("http://cache.example.com")
        backend.has_requests = True

        mock_response = Mock()
        mock_response.status_code = 200

        mock_requests = Mock()
        mock_requests.head.return_value = mock_response
        backend.requests = mock_requests

        exists = backend.exists("test_key")
        assert exists is True

    def test_exists_false(self):
        """Test exists check for missing key."""
        backend = HTTPBackend("http://cache.example.com")
        backend.has_requests = True

        mock_response = Mock()
        mock_response.status_code = 404

        mock_requests = Mock()
        mock_requests.head.return_value = mock_response
        backend.requests = mock_requests

        exists = backend.exists("missing")
        assert exists is False


class TestRedisBackend:
    """Tests for RedisBackend."""

    def test_init_without_redis(self):
        """Test initialization when redis is not available."""
        backend = RedisBackend()
        backend.has_redis = False
        backend.prefix = "test:"

        result = backend.get("test")
        assert result is None

    def test_make_key(self):
        """Test key prefixing."""
        backend = RedisBackend(prefix="myapp:")
        backend.has_redis = False  # Don't actually connect

        key = backend._make_key("test")
        assert key == "myapp:test"

    def test_get_success(self):
        """Test getting data from Redis."""
        backend = RedisBackend()
        backend.has_redis = True

        mock_redis = Mock()
        mock_redis.get.return_value = json.dumps({"data": "value"}).encode()
        backend.redis_client = mock_redis

        result = backend.get("test_key")
        assert result == {"data": "value"}

    def test_set_success(self):
        """Test setting data to Redis."""
        backend = RedisBackend()
        backend.has_redis = True

        mock_redis = Mock()
        backend.redis_client = mock_redis

        success = backend.set("test_key", {"data": "value"})
        assert success is True
        mock_redis.set.assert_called_once()

    def test_delete_success(self):
        """Test deleting from Redis."""
        backend = RedisBackend()
        backend.has_redis = True

        mock_redis = Mock()
        backend.redis_client = mock_redis

        success = backend.delete("test_key")
        assert success is True
        mock_redis.delete.assert_called_once()

    def test_exists_true(self):
        """Test exists check in Redis."""
        backend = RedisBackend()
        backend.has_redis = True

        mock_redis = Mock()
        mock_redis.exists.return_value = 1
        backend.redis_client = mock_redis

        exists = backend.exists("test_key")
        assert exists is True


class TestS3Backend:
    """Tests for S3Backend."""

    def test_init_without_boto3(self):
        """Test initialization when boto3 is not available."""
        backend = S3Backend("my-bucket")
        backend.has_boto3 = False
        backend.bucket = "my-bucket"
        backend.prefix = "cache/"

        result = backend.get("test")
        assert result is None

    def test_make_key(self):
        """Test key prefixing."""
        backend = S3Backend("my-bucket", prefix="app/cache/")
        backend.has_boto3 = False

        key = backend._make_key("test")
        assert key == "app/cache/test"

    def test_get_success(self):
        """Test getting data from S3."""
        backend = S3Backend("my-bucket")
        backend.has_boto3 = True

        mock_s3 = Mock()
        mock_response = {
            "Body": Mock(read=lambda: json.dumps({"data": "value"}).encode())
        }
        mock_s3.get_object.return_value = mock_response
        backend.s3_client = mock_s3

        result = backend.get("test_key")
        assert result == {"data": "value"}

    def test_set_success(self):
        """Test setting data to S3."""
        backend = S3Backend("my-bucket")
        backend.has_boto3 = True

        mock_s3 = Mock()
        backend.s3_client = mock_s3

        success = backend.set("test_key", {"data": "value"})
        assert success is True
        mock_s3.put_object.assert_called_once()

        mock_s3 = Mock()
        mock_s3.head_object.return_value = {}
        backend.s3_client = mock_s3

        exists = backend.exists("test_key")
        assert exists is True


class TestCreateBackend:
    """Tests for create_backend function."""

    def test_file_backend(self, tmp_path):
        """Test creating file share backend."""
        backend = create_backend(f"file://{tmp_path}/cache")
        assert isinstance(backend, FileShareBackend)

    def test_http_backend(self):
        """Test creating HTTP backend."""
        backend = create_backend("http://cache.example.com")
        assert isinstance(backend, HTTPBackend)

    def test_https_backend(self):
        """Test creating HTTPS backend."""
        backend = create_backend("https://cache.example.com")
        assert isinstance(backend, HTTPBackend)

    def test_redis_backend(self):
        """Test creating Redis backend."""
        backend = create_backend("redis://localhost:6379/0")
        assert isinstance(backend, RedisBackend)

    def test_s3_backend(self):
        """Test creating S3 backend."""
        backend = create_backend("s3://my-bucket/prefix")
        assert isinstance(backend, S3Backend)

    def test_unsupported_scheme(self):
        """Test handling of unsupported URL scheme."""
        backend = create_backend("ftp://example.com")
        assert backend is None


class TestGetRemoteCacheUrl:
    """Tests for get_remote_cache_url function."""

    def test_from_py_smart_test_env(self):
        """Test reading from PY_SMART_TEST_REMOTE_CACHE."""
        with patch.dict("os.environ", {"PY_SMART_TEST_REMOTE_CACHE": "http://cache"}):
            url = get_remote_cache_url()
            assert url == "http://cache"

    def test_from_remote_cache_url_env(self):
        """Test reading from REMOTE_CACHE_URL."""
        with patch.dict("os.environ", {"REMOTE_CACHE_URL": "http://cache2"}):
            url = get_remote_cache_url()
            assert url == "http://cache2"

    def test_priority(self):
        """Test that PY_SMART_TEST_REMOTE_CACHE takes priority."""
        with patch.dict(
            "os.environ",
            {
                "PY_SMART_TEST_REMOTE_CACHE": "http://cache1",
                "REMOTE_CACHE_URL": "http://cache2",
            },
        ):
            url = get_remote_cache_url()
            assert url == "http://cache1"

    def test_no_env_var(self):
        """Test when no environment variable is set."""
        with patch.dict("os.environ", {}, clear=True):
            url = get_remote_cache_url()
            assert url is None


class TestGetRemoteCacheBackend:
    """Tests for get_remote_cache_backend function."""

    def test_with_valid_url(self, tmp_path):
        """Test getting backend with valid URL."""
        with patch.dict(
            "os.environ", {"PY_SMART_TEST_REMOTE_CACHE": f"file://{tmp_path}"}
        ):
            backend = get_remote_cache_backend()
            assert isinstance(backend, FileShareBackend)

    def test_without_url(self):
        """Test when no URL is configured."""
        with patch.dict("os.environ", {}, clear=True):
            backend = get_remote_cache_backend()
            assert backend is None

    def test_with_invalid_url(self):
        """Test with invalid URL scheme."""
        with patch.dict("os.environ", {"PY_SMART_TEST_REMOTE_CACHE": "invalid://url"}):
            backend = get_remote_cache_backend()
            assert backend is None
