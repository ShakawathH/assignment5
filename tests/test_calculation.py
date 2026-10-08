import pytest
from decimal import Decimal
from datetime import datetime
from app.calculation import Calculation
from app.exceptions import OperationError
from app.calculator_memento import CalculatorMemento
import logging


def test_addition():
    calc = Calculation(operation="Addition", operand1=Decimal("2"), operand2=Decimal("3"))
    assert calc.result == Decimal("5")


def test_subtraction():
    calc = Calculation(operation="Subtraction", operand1=Decimal("5"), operand2=Decimal("3"))
    assert calc.result == Decimal("2")


def test_multiplication():
    calc = Calculation(operation="Multiplication", operand1=Decimal("4"), operand2=Decimal("2"))
    assert calc.result == Decimal("8")


def test_division():
    calc = Calculation(operation="Division", operand1=Decimal("8"), operand2=Decimal("2"))
    assert calc.result == Decimal("4")


def test_division_by_zero():
    with pytest.raises(OperationError, match="Division by zero is not allowed"):
        Calculation(operation="Division", operand1=Decimal("8"), operand2=Decimal("0"))


def test_power():
    calc = Calculation(operation="Power", operand1=Decimal("2"), operand2=Decimal("3"))
    assert calc.result == Decimal("8")


def test_negative_power():
    with pytest.raises(OperationError, match="Negative exponents are not supported"):
        Calculation(operation="Power", operand1=Decimal("2"), operand2=Decimal("-3"))


def test_root():
    calc = Calculation(operation="Root", operand1=Decimal("16"), operand2=Decimal("2"))
    assert calc.result == Decimal("4")


def test_invalid_root():
    with pytest.raises(OperationError, match="Cannot calculate root of negative number"):
        Calculation(operation="Root", operand1=Decimal("-16"), operand2=Decimal("2"))


def test_unknown_operation():
    with pytest.raises(OperationError, match="Unknown operation"):
        Calculation(operation="Unknown", operand1=Decimal("5"), operand2=Decimal("3"))


def test_to_dict():
    calc = Calculation(operation="Addition", operand1=Decimal("2"), operand2=Decimal("3"))
    result_dict = calc.to_dict()
    assert result_dict == {
        "operation": "Addition",
        "operand1": "2",
        "operand2": "3",
        "result": "5",
        "timestamp": calc.timestamp.isoformat()
    }


def test_from_dict():
    data = {
        "operation": "Addition",
        "operand1": "2",
        "operand2": "3",
        "result": "5",
        "timestamp": datetime.now().isoformat()
    }
    calc = Calculation.from_dict(data)
    assert calc.operation == "Addition"
    assert calc.operand1 == Decimal("2")
    assert calc.operand2 == Decimal("3")
    assert calc.result == Decimal("5")


def test_invalid_from_dict():
    data = {
        "operation": "Addition",
        "operand1": "invalid",
        "operand2": "3",
        "result": "5",
        "timestamp": datetime.now().isoformat()
    }
    with pytest.raises(OperationError, match="Invalid calculation data"):
        Calculation.from_dict(data)


def test_format_result():
    calc = Calculation(operation="Division", operand1=Decimal("1"), operand2=Decimal("3"))
    assert calc.format_result(precision=2) == "0.33"
    assert calc.format_result(precision=10) == "0.3333333333"


def test_equality():
    calc1 = Calculation(operation="Addition", operand1=Decimal("2"), operand2=Decimal("3"))
    calc2 = Calculation(operation="Addition", operand1=Decimal("2"), operand2=Decimal("3"))
    calc3 = Calculation(operation="Subtraction", operand1=Decimal("5"), operand2=Decimal("3"))
    assert calc1 == calc2
    assert calc1 != calc3


# New Test to Cover Logging Warning
def test_from_dict_result_mismatch(caplog):
    """
    Test the from_dict method to ensure it logs a warning when the saved result
    does not match the computed result.
    """
    # Arrange
    data = {
        "operation": "Addition",
        "operand1": "2",
        "operand2": "3",
        "result": "10",  # Incorrect result to trigger logging.warning
        "timestamp": datetime.now().isoformat()
    }

    # Act
    with caplog.at_level(logging.WARNING):
        calc = Calculation.from_dict(data)

    # Assert
    assert "Loaded calculation result 10 differs from computed result 5" in caplog.text

def test_calculation_str():
    calc = Calculation("Addition", Decimal("2"), Decimal("3"))
    assert str(calc) == "Addition(2, 3) = 5"

def test_calculation_repr():
    calc = Calculation("Addition", Decimal("2"), Decimal("3"))
    result = repr(calc)
    assert result.startswith("Calculation(operation='Addition'")
    assert "operand1=2" in result
    assert "operand2=3" in result
    assert "result=5" in result
    assert f"timestamp='{calc.timestamp.isoformat()}'" in result

def test_calculation_eq_with_non_calculation():
    calc = Calculation("Addition", Decimal("2"), Decimal("3"))

    # Calling __eq__ directly shows the NotImplemented return value
    assert calc.__eq__("not a calculation") is NotImplemented

    # Using == makes Python fall back to identity comparison, so it ends up False
    assert calc != "not a calculation"
    assert calc != 5

def test_calculation_eq_with_calculation():
    calc1 = Calculation("Addition", Decimal("2"), Decimal("3"))
    calc2 = Calculation("Addition", Decimal("2"), Decimal("3"))
    calc3 = Calculation("Subtraction", Decimal("5"), Decimal("3"))

    assert calc1 == calc2
    assert calc1 != calc3

def test_memento_to_dict():
    calc = Calculation("Addition", Decimal("2"), Decimal("3"))
    memento = CalculatorMemento(history=[calc])

    data = memento.to_dict()

    assert data['history'] == [calc.to_dict()]
    assert data['timestamp'] == memento.timestamp.isoformat()


def test_memento_from_dict():
    calc = Calculation("Addition", Decimal("2"), Decimal("3"))
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    data = {
        'history': [calc.to_dict()],
        'timestamp': timestamp.isoformat()
    }

    memento = CalculatorMemento.from_dict(data)

    assert len(memento.history) == 1
    assert memento.history[0] == calc
    assert memento.timestamp == timestamp


def test_memento_round_trip():
    calc1 = Calculation("Addition", Decimal("2"), Decimal("3"))
    calc2 = Calculation("Multiplication", Decimal("4"), Decimal("5"))
    original = CalculatorMemento(history=[calc1, calc2])

    restored = CalculatorMemento.from_dict(original.to_dict())

    assert restored.history == original.history
    assert restored.timestamp == original.timestamp

def test_power_overflow_raises_operation_error():
    with pytest.raises(OperationError, match="Calculation failed"):
        Calculation("Power", Decimal("10"), Decimal("1000"))


def test_multiplication_overflow_raises_operation_error():
    with pytest.raises(OperationError, match="Calculation failed"):
        Calculation("Multiplication", Decimal("1E999999999"), Decimal("1E999999999"))