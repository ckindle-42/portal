"""
Tests for AST-based safe math evaluator in MathVisualizer (Task 1.2).

Verifies: valid formulas produce correct output, and exploit attempts raise ValueError.
"""

import pytest

from portal.tools.data_tools.math_visualizer import _safe_eval

np = pytest.importorskip("numpy")


class TestSafeEval:
    """Test _safe_eval correctness and security boundaries."""

    # ------------------------------------------------------------------
    # Correctness tests
    # ------------------------------------------------------------------

    def test_constant(self):
        x = np.array([1.0, 2.0, 3.0])
        result = _safe_eval("42", x)
        assert result == 42

    def test_identity(self):
        x = np.array([1.0, 2.0, 3.0])
        np.testing.assert_array_equal(_safe_eval("x", x), x)

    def test_polynomial(self):
        x = np.array([0.0, 1.0, 2.0])
        result = _safe_eval("x**2 + 2*x + 1", x)
        expected = x**2 + 2 * x + 1
        np.testing.assert_allclose(result, expected)

    def test_sin(self):
        x = np.linspace(0, np.pi, 10)
        result = _safe_eval("sin(x)", x)
        np.testing.assert_allclose(result, np.sin(x))

    def test_cos(self):
        x = np.linspace(0, np.pi, 10)
        result = _safe_eval("cos(x)", x)
        np.testing.assert_allclose(result, np.cos(x))

    def test_nested_functions(self):
        x = np.array([1.0, 2.0, 4.0])
        result = _safe_eval("sqrt(abs(x))", x)
        np.testing.assert_allclose(result, np.sqrt(np.abs(x)))

    def test_pi_constant(self):
        x = np.array([1.0])
        result = _safe_eval("pi", x)
        assert result == pytest.approx(np.pi)

    def test_e_constant(self):
        x = np.array([1.0])
        result = _safe_eval("e", x)
        assert result == pytest.approx(np.e)

    def test_division(self):
        x = np.array([2.0, 4.0])
        result = _safe_eval("x / 2", x)
        np.testing.assert_allclose(result, x / 2)

    def test_negation(self):
        x = np.array([3.0])
        result = _safe_eval("-x", x)
        np.testing.assert_allclose(result, -x)

    # ------------------------------------------------------------------
    # Security / exploit tests
    # ------------------------------------------------------------------

    def test_import_raises(self):
        """__import__('os') must raise ValueError, not execute."""
        x = np.array([1.0])
        with pytest.raises((ValueError, AttributeError)):
            _safe_eval("__import__('os')", x)

    def test_open_raises(self):
        """open('/etc/passwd') must raise ValueError."""
        x = np.array([1.0])
        with pytest.raises((ValueError, AttributeError)):
            _safe_eval("open('/etc/passwd')", x)

    def test_exec_raises(self):
        """exec() call must raise ValueError."""
        x = np.array([1.0])
        with pytest.raises((ValueError, AttributeError)):
            _safe_eval("exec('import os')", x)

    def test_unknown_variable_raises(self):
        """An undefined variable name must raise ValueError."""
        x = np.array([1.0])
        with pytest.raises(ValueError, match="Unknown variable"):
            _safe_eval("y + 1", x)

    def test_unknown_function_raises(self):
        """A function not in _SAFE_FUNCS must raise ValueError."""
        x = np.array([1.0])
        with pytest.raises(ValueError, match="Unknown function"):
            _safe_eval("evil(x)", x)

    def test_attribute_access_raises(self):
        """Attribute-access expressions must raise ValueError."""
        x = np.array([1.0])
        with pytest.raises(ValueError):
            _safe_eval("x.__class__", x)

    def test_list_literal_raises(self):
        """List literals are not supported and must raise ValueError."""
        x = np.array([1.0])
        with pytest.raises(ValueError):
            _safe_eval("[1, 2, 3]", x)
