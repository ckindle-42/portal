"""
Tests for pickle deserialization gating in KnowledgeBaseSQLite (Task 1.3).

Verifies:
- Default (ALLOW_LEGACY_PICKLE_EMBEDDINGS unset/false): returns None on pickle blob
- With env flag enabled: correctly deserializes the pickle blob
"""

import pickle

import numpy as np


def _make_instance():
    """Create a EnhancedKnowledgeTool instance (no DB needed for unit test)."""
    from portal.tools.knowledge.knowledge_base_sqlite import EnhancedKnowledgeTool
    import unittest.mock as mock
    with mock.patch("sqlite3.connect"):
        inst = EnhancedKnowledgeTool.__new__(EnhancedKnowledgeTool)
        inst.conn = None
        inst.db_path = ":memory:"
    return inst


def _pickle_blob(arr: np.ndarray) -> bytes:
    """Serialize a numpy array as pickle bytes (legacy format)."""
    return pickle.dumps(arr)


class TestPickleGating:

    def test_default_returns_none_for_pickle_blob(self, monkeypatch):
        """Without the env flag, pickle blobs must return None."""
        monkeypatch.delenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", raising=False)
        instance = _make_instance()
        arr = np.array([0.1, 0.2, 0.3])
        blob = _pickle_blob(arr)
        result = instance._deserialize_embedding(blob)
        assert result is None

    def test_flag_false_returns_none(self, monkeypatch):
        """Explicit 'false' value must still return None."""
        monkeypatch.setenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", "false")
        instance = _make_instance()
        arr = np.array([0.1, 0.2, 0.3])
        blob = _pickle_blob(arr)
        result = instance._deserialize_embedding(blob)
        assert result is None

    def test_flag_enabled_loads_correctly(self, monkeypatch):
        """With the env flag set to 'true', the pickle blob should load."""
        monkeypatch.setenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", "true")
        instance = _make_instance()
        arr = np.array([0.1, 0.2, 0.3])
        blob = _pickle_blob(arr)
        result = instance._deserialize_embedding(blob)
        assert result is not None
        np.testing.assert_allclose(result, arr)

    def test_flag_enabled_1_loads_correctly(self, monkeypatch):
        """Env flag value '1' should also enable pickle loading."""
        monkeypatch.setenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", "1")
        instance = _make_instance()
        arr = np.array([1.0, 2.0])
        blob = _pickle_blob(arr)
        result = instance._deserialize_embedding(blob)
        assert result is not None
        np.testing.assert_allclose(result, arr)

    def test_json_blob_always_works(self, monkeypatch):
        """JSON-encoded embeddings must always load regardless of the flag."""
        monkeypatch.delenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", raising=False)
        import json
        instance = _make_instance()
        arr = np.array([0.5, 0.6, 0.7])
        json_blob = json.dumps(arr.tolist()).encode("utf-8")
        result = instance._deserialize_embedding(json_blob)
        assert result is not None
        np.testing.assert_allclose(result, arr)

    def test_flag_yes_loads_correctly(self, monkeypatch):
        """Env flag value 'yes' should also enable pickle loading."""
        monkeypatch.setenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", "yes")
        instance = _make_instance()
        arr = np.array([3.0, 4.0])
        blob = _pickle_blob(arr)
        result = instance._deserialize_embedding(blob)
        assert result is not None
        np.testing.assert_allclose(result, arr)
