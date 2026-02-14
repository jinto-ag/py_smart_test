"""Tests for test_prioritizer module."""

from py_smart_test.test_prioritizer import prioritize_tests


class TestPrioritizeTests:
    def test_failed_first(self):
        all_tests = ["a", "b", "c", "d"]
        affected = {"b", "c"}
        failed = {"d"}
        durations = {}

        result = prioritize_tests(all_tests, affected, failed, durations)
        assert result[0] == "d"  # failed test comes first

    def test_affected_before_rest(self):
        all_tests = ["a", "b", "c"]
        affected = {"c"}
        failed = set()
        durations = {}

        result = prioritize_tests(all_tests, affected, failed, durations)
        # "c" should come before "a" and "b"
        assert result.index("c") < result.index("a")
        assert result.index("c") < result.index("b")

    def test_faster_tests_first_within_bucket(self):
        all_tests = ["slow", "fast", "medium"]
        affected = {"slow", "fast", "medium"}
        failed = set()
        durations = {"slow": 5.0, "fast": 0.1, "medium": 1.0}

        result = prioritize_tests(all_tests, affected, failed, durations)
        assert result == ["fast", "medium", "slow"]

    def test_full_priority_order(self):
        """Failed → affected → rest, each sorted by duration."""
        all_tests = [
            "rest_slow",
            "rest_fast",
            "aff_slow",
            "aff_fast",
            "fail_slow",
            "fail_fast",
        ]
        affected = {"aff_slow", "aff_fast"}
        failed = {"fail_slow", "fail_fast"}
        durations = {
            "fail_fast": 0.1,
            "fail_slow": 2.0,
            "aff_fast": 0.2,
            "aff_slow": 3.0,
            "rest_fast": 0.3,
            "rest_slow": 4.0,
        }

        result = prioritize_tests(all_tests, affected, failed, durations)
        assert result == [
            "fail_fast",
            "fail_slow",
            "aff_fast",
            "aff_slow",
            "rest_fast",
            "rest_slow",
        ]

    def test_empty_input(self):
        assert prioritize_tests([], set(), set(), {}) == []

    def test_no_affected_no_failed(self):
        all_tests = ["a", "b"]
        result = prioritize_tests(all_tests, set(), set(), {})
        assert set(result) == {"a", "b"}

    def test_unknown_durations_sorted_last(self):
        all_tests = ["known", "unknown"]
        affected = {"known", "unknown"}
        durations = {"known": 0.5}

        result = prioritize_tests(all_tests, affected, set(), durations)
        assert result[0] == "known"
        assert result[1] == "unknown"
