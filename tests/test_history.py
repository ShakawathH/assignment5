import pytest
from unittest.mock import Mock, patch
from app.calculation import Calculation
from app.history import LoggingObserver, AutoSaveObserver
from app.calculator import Calculator
from app.calculator_config import CalculatorConfig

# Sample setup for mock calculation
calculation_mock = Mock(spec=Calculation)
calculation_mock.operation = "addition"
calculation_mock.operand1 = 5
calculation_mock.operand2 = 3
calculation_mock.result = 8

# Test cases for LoggingObserver

@patch('logging.info')
def test_logging_observer_logs_calculation(logging_info_mock):
    observer = LoggingObserver()
    observer.update(calculation_mock)
    logging_info_mock.assert_called_once_with(
        "Calculation performed: addition (5, 3) = 8"
    )

def test_logging_observer_no_calculation():
    observer = LoggingObserver()
    with pytest.raises(AttributeError):
        observer.update(None)  # Passing None should raise an exception as there's no calculation

# Test cases for AutoSaveObserver

def test_autosave_observer_triggers_save():
    calculator_mock = Mock(spec=Calculator)
    calculator_mock.config = Mock(spec=CalculatorConfig)
    calculator_mock.config.auto_save = True
    observer = AutoSaveObserver(calculator_mock)
    
    observer.update(calculation_mock)
    calculator_mock.save_history.assert_called_once()

@patch('logging.info')
def test_autosave_observer_logs_autosave(logging_info_mock):
    calculator_mock = Mock(spec=Calculator)
    calculator_mock.config = Mock(spec=CalculatorConfig)
    calculator_mock.config.auto_save = True
    observer = AutoSaveObserver(calculator_mock)
    
    observer.update(calculation_mock)
    logging_info_mock.assert_called_once_with("History auto-saved")

def test_autosave_observer_does_not_trigger_save_when_disabled():
    calculator_mock = Mock(spec=Calculator)
    calculator_mock.config = Mock(spec=CalculatorConfig)
    calculator_mock.config.auto_save = False
    observer = AutoSaveObserver(calculator_mock)
    
    observer.update(calculation_mock)
    calculator_mock.save_history.assert_not_called()

# Additional negative test cases for AutoSaveObserver

def test_autosave_observer_invalid_calculator():
    with pytest.raises(TypeError):
        AutoSaveObserver(None)  # Passing None should raise a TypeError

def test_autosave_observer_no_calculation():
    calculator_mock = Mock(spec=Calculator)
    calculator_mock.config = Mock(spec=CalculatorConfig)
    calculator_mock.config.auto_save = True
    observer = AutoSaveObserver(calculator_mock)
    
    with pytest.raises(AttributeError):
        observer.update(None)  # Passing None should raise an exception

def test_init_logs_warning_when_history_load_fails(tmp_path):
    config = CalculatorConfig(base_dir=tmp_path)

    with patch.object(Calculator, "load_history", side_effect=Exception("boom")), \
         patch("app.calculator.logging.warning") as mock_warning:
        calc = Calculator(config)

    # Calculator still initializes despite the failure
    assert calc.history == []
    mock_warning.assert_called_once()
    assert "Could not load existing history: boom" in mock_warning.call_args[0][0]

def test_init_handles_corrupt_history_file(tmp_path):
    config = CalculatorConfig(base_dir=tmp_path)
    config.history_dir.mkdir(parents=True, exist_ok=True)
    # Missing required columns -> KeyError inside load_history -> OperationError
    config.history_file.write_text("bad,columns\n1,2\n")

    calc = Calculator(config)

    assert calc.history == []

def test_setup_logging_failure_prints_and_reraises(tmp_path, capsys):
    config = CalculatorConfig(base_dir=tmp_path)

    with patch("app.calculator.logging.basicConfig", side_effect=OSError("disk error")):
        with pytest.raises(OSError, match="disk error"):
            Calculator(config)

    assert "Error setting up logging: disk error" in capsys.readouterr().out