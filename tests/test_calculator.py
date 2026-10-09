import datetime
from types import SimpleNamespace
from pathlib import Path
import pandas as pd
import pytest
from unittest.mock import Mock, patch, PropertyMock, MagicMock
from decimal import Decimal
from tempfile import TemporaryDirectory
from app.calculator import Calculator
from app.calculator_repl import calculator_repl
from app.calculator_config import CalculatorConfig
from app.exceptions import OperationError, ValidationError
from app.history import LoggingObserver, AutoSaveObserver
from app.operations import OperationFactory

# Fixture to initialize Calculator with a temporary directory for file paths
@pytest.fixture
def calculator():
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = CalculatorConfig(base_dir=temp_path)

        # Patch properties to use the temporary directory paths
        with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
             patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file, \
             patch.object(CalculatorConfig, 'history_dir', new_callable=PropertyMock) as mock_history_dir, \
             patch.object(CalculatorConfig, 'history_file', new_callable=PropertyMock) as mock_history_file:
            
            # Set return values to use paths within the temporary directory
            mock_log_dir.return_value = temp_path / "logs"
            mock_log_file.return_value = temp_path / "logs/calculator.log"
            mock_history_dir.return_value = temp_path / "history"
            mock_history_file.return_value = temp_path / "history/calculator_history.csv"
            
            # Return an instance of Calculator with the mocked config
            yield Calculator(config=config)

# Test Calculator Initialization

def test_calculator_initialization(calculator):
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []
    assert calculator.operation_strategy is None

# Test Logging Setup

@patch('app.calculator.logging.info')
def test_logging_setup(logging_info_mock):
    with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
         patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file:
        mock_log_dir.return_value = Path('/tmp/logs')
        mock_log_file.return_value = Path('/tmp/logs/calculator.log')
        
        # Instantiate calculator to trigger logging
        calculator = Calculator(CalculatorConfig())
        logging_info_mock.assert_any_call("Calculator initialized with configuration")

# Test Adding and Removing Observers

def test_add_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    assert observer in calculator.observers

def test_remove_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    calculator.remove_observer(observer)
    assert observer not in calculator.observers

# Test Setting Operations

def test_set_operation(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    assert calculator.operation_strategy == operation

# Test Performing Operations

def test_perform_operation_addition(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    result = calculator.perform_operation(2, 3)
    assert result == Decimal('5')

def test_perform_operation_validation_error(calculator):
    calculator.set_operation(OperationFactory.create_operation('add'))
    with pytest.raises(ValidationError):
        calculator.perform_operation('invalid', 3)

def test_perform_operation_operation_error(calculator):
    with pytest.raises(OperationError, match="No operation set"):
        calculator.perform_operation(2, 3)

# Test Undo/Redo Functionality

def test_undo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    assert calculator.history == []

def test_redo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    calculator.redo()
    assert len(calculator.history) == 1

# Test History Management

@patch('app.calculator.pd.DataFrame.to_csv')
def test_save_history(mock_to_csv, calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.save_history()
    mock_to_csv.assert_called_once()

@patch('app.calculator.pd.read_csv')
@patch('app.calculator.Path.exists', return_value=True)
def test_load_history(mock_exists, mock_read_csv, calculator):
    # Mock CSV data to match the expected format in from_dict
    mock_read_csv.return_value = pd.DataFrame({
        'operation': ['Addition'],
        'operand1': ['2'],
        'operand2': ['3'],
        'result': ['5'],
        'timestamp': [datetime.datetime.now().isoformat()]
    })
    
    # Test the load_history functionality
    try:
        calculator.load_history()
        # Verify history length after loading
        assert len(calculator.history) == 1
        # Verify the loaded values
        assert calculator.history[0].operation == "Addition"
        assert calculator.history[0].operand1 == Decimal("2")
        assert calculator.history[0].operand2 == Decimal("3")
        assert calculator.history[0].result == Decimal("5")
    except OperationError:
        pytest.fail("Loading history failed due to OperationError")
        
            
# Test Clearing History

def test_clear_history(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.clear_history()
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []

# Test REPL Commands (using patches for input/output handling)

@patch('builtins.input', side_effect=['exit'])
@patch('builtins.print')
def test_calculator_repl_exit(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history') as mock_save_history:
        calculator_repl()
        mock_save_history.assert_called_once()
        mock_print.assert_any_call("History saved successfully.")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['help', 'exit'])
@patch('builtins.print')
def test_calculator_repl_help(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nAvailable commands:")

@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_addition(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nResult: 5")

def test_history_trimmed_when_exceeding_max_size(tmp_path):
    config = CalculatorConfig(base_dir=tmp_path)
    calc = Calculator(config)

    calc.history.clear()          # drop anything loaded from a real file
    calc.config.max_history_size = 2

    calc.set_operation(OperationFactory.create_operation("add"))
    calc.perform_operation("1", "1")
    calc.perform_operation("2", "2")
    calc.perform_operation("3", "3")

    assert len(calc.history) == 2
    assert calc.history[0].operand1 == Decimal("2")
    assert calc.history[1].operand1 == Decimal("3")

def test_perform_operation_wraps_unexpected_errors(tmp_path):
    calc = Calculator(CalculatorConfig(base_dir=tmp_path))
    history_before = len(calc.history)

    failing_operation = MagicMock()
    failing_operation.execute.side_effect = RuntimeError("kaboom")
    calc.set_operation(failing_operation)

    with pytest.raises(OperationError, match="Operation failed: kaboom"):
        calc.perform_operation("1", "2")

    # The failure happens before the calculation is recorded
    assert len(calc.history) == history_before

def test_perform_operation_reraises_validation_error(tmp_path):
    calc = Calculator(CalculatorConfig(base_dir=tmp_path))
    calc.set_operation(MagicMock())

    with pytest.raises(ValidationError):
        calc.perform_operation("not-a-number", "2")

def test_save_history_empty_writes_headers_only(tmp_path):
    calc = Calculator(CalculatorConfig(base_dir=tmp_path))
    calc.history.clear()  # force the "else" branch

    with patch("app.calculator.pd.DataFrame.to_csv", autospec=True) as mock_to_csv:
        calc.save_history()

    mock_to_csv.assert_called_once()
    df_written = mock_to_csv.call_args[0][0]  # autospec passes the DataFrame as self
    assert df_written.empty
    assert list(df_written.columns) == [
        "operation", "operand1", "operand2", "result", "timestamp"
    ]


def test_save_history_failure_raises_operation_error(tmp_path):
    calc = Calculator(CalculatorConfig(base_dir=tmp_path))

    with patch("app.calculator.pd.DataFrame.to_csv", side_effect=OSError("disk full")):
        with pytest.raises(OperationError, match="Failed to save history: disk full"):
            calc.save_history()

def test_load_history_empty_file_logs_and_keeps_history(tmp_path):
    calc = Calculator(CalculatorConfig(base_dir=tmp_path))
    history_before = list(calc.history)

    empty_df = pd.DataFrame(
        columns=["operation", "operand1", "operand2", "result", "timestamp"]
    )

    with patch.object(Path, "exists", return_value=True), \
         patch("app.calculator.pd.read_csv", return_value=empty_df), \
         patch("app.calculator.logging.info") as mock_info:
        calc.load_history()

    mock_info.assert_called_once_with("Loaded empty history file")
    # An empty file doesn't reset the in-memory history
    assert calc.history == history_before

def test_get_history_dataframe_returns_expected_columns_and_values(tmp_path):
    calc = Calculator(CalculatorConfig(base_dir=tmp_path))

    ts = datetime.datetime(2024, 1, 1, 12, 0, 0)
    calc.history = [
        SimpleNamespace(operation="Addition", operand1=1, operand2=2, result=3, timestamp=ts),
        SimpleNamespace(operation="Subtraction", operand1=5, operand2=4, result=1, timestamp=ts),
    ]

    df = calc.get_history_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["operation", "operand1", "operand2", "result", "timestamp"]
    assert len(df) == 2
    assert df.iloc[0]["operation"] == "Addition"
    assert df.iloc[0]["operand1"] == "1"      # values are converted with str()
    assert df.iloc[0]["result"] == "3"
    assert df.iloc[1]["operand2"] == "4"
    assert df.iloc[0]["timestamp"] == ts      # timestamp is kept as a datetime, not a string

def test_show_history_returns_formatted_strings(tmp_path):
    calc = Calculator(CalculatorConfig(base_dir=tmp_path))

    calc.history = [
        SimpleNamespace(operation="Addition", operand1=1, operand2=2, result=3),
        SimpleNamespace(operation="Subtraction", operand1=5, operand2=4, result=1),
    ]

    assert calc.show_history() == [
        "Addition(1, 2) = 3",
        "Subtraction(5, 4) = 1",
    ]

def test_exit_save_history_failure(capsys):
    with patch('builtins.input', side_effect=['exit']), \
         patch('app.calculator.Calculator.save_history',
               side_effect=Exception("disk full")):
        calculator_repl()

    output = capsys.readouterr().out
    assert "Warning: Could not save history: disk full" in output
    assert "Goodbye!" in output

def test_history_empty(capsys):
    with patch('builtins.input', side_effect=['history', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.show_history', return_value=[]):
        calculator_repl()

    output = capsys.readouterr().out
    assert "No calculations in history" in output


def test_history_with_entries(capsys):
    with patch('builtins.input', side_effect=['add', '2', '3', 'history', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()

    output = capsys.readouterr().out
    assert "Calculation History:" in output
    assert "1. " in output

def test_clear_history(capsys):
    with patch('builtins.input', side_effect=['clear', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()

    output = capsys.readouterr().out
    assert "History cleared" in output

def test_clear_history_removes_entries(capsys):
    with patch('builtins.input', side_effect=['add', '2', '3', 'clear', 'history', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()

    output = capsys.readouterr().out
    assert "History cleared" in output
    assert "No calculations in history" in output

def test_undo_nothing_to_undo(capsys):
    with patch('builtins.input', side_effect=['undo', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.undo', return_value=False):
        calculator_repl()

    output = capsys.readouterr().out
    assert "Nothing to undo" in output


def test_undo_success(capsys):
    with patch('builtins.input', side_effect=['add', '2', '3', 'undo', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()

    output = capsys.readouterr().out
    assert "Operation undone" in output

def test_redo_nothing_to_redo(capsys):
    with patch('builtins.input', side_effect=['redo', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.redo', return_value=False):
        calculator_repl()

    output = capsys.readouterr().out
    assert "Nothing to redo" in output


def test_redo_success(capsys):
    with patch('builtins.input', side_effect=['add', '2', '3', 'undo', 'redo', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()

    output = capsys.readouterr().out
    assert "Operation redone" in output

def test_save_success(capsys):
    with patch('builtins.input', side_effect=['save', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()

    output = capsys.readouterr().out
    assert "History saved successfully" in output


def test_save_error(capsys):
    with patch('builtins.input', side_effect=['save', 'exit']), \
         patch('app.calculator.Calculator.save_history',
               side_effect=Exception("disk full")):
        calculator_repl()

    output = capsys.readouterr().out
    assert "Error saving history: disk full" in output

def test_cancel_first_number(capsys):
    with patch('builtins.input', side_effect=['add', 'cancel', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()

    output = capsys.readouterr().out
    assert "Operation cancelled" in output

def test_cancel_second_number(capsys):
    with patch('builtins.input', side_effect=['add', '2', 'cancel', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()

    output = capsys.readouterr().out
    assert "Operation cancelled" in output

def test_validation_error(capsys):
    with patch('builtins.input', side_effect=['add', 'abc', '2', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.perform_operation',
               side_effect=ValidationError("bad input")):
        calculator_repl()

    assert "Error: bad input" in capsys.readouterr().out


def test_operation_error(capsys):
    with patch('builtins.input', side_effect=['add', '2', '3', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.perform_operation',
               side_effect=OperationError("op failed")):
        calculator_repl()

    assert "Error: op failed" in capsys.readouterr().out


def test_unexpected_error_in_operation(capsys):
    with patch('builtins.input', side_effect=['add', '2', '3', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.perform_operation',
               side_effect=RuntimeError("boom")):
        calculator_repl()

    assert "Unexpected error: boom" in capsys.readouterr().out

def test_unknown_command(capsys):
    with patch('builtins.input', side_effect=['foo', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()

    assert "Unknown command: 'foo'" in capsys.readouterr().out


def test_keyboard_interrupt(capsys):
    with patch('builtins.input', side_effect=[KeyboardInterrupt, 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()

    assert "Operation cancelled" in capsys.readouterr().out


def test_eof_error(capsys):
    with patch('builtins.input', side_effect=EOFError):
        calculator_repl()

    assert "Input terminated. Exiting..." in capsys.readouterr().out


def test_loop_level_exception(capsys):
    with patch('builtins.input', side_effect=['history', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.show_history',
               side_effect=Exception("history broke")):
        calculator_repl()

    assert "Error: history broke" in capsys.readouterr().out


def test_fatal_error_on_init(capsys):
    with patch('app.calculator_repl.Calculator',
               side_effect=Exception("init failed")):
        with pytest.raises(Exception, match="init failed"):
            calculator_repl()

    assert "Fatal error: init failed" in capsys.readouterr().out

######

def test_load_success(capsys):
    with patch('builtins.input', side_effect=['load', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.load_history'):
        calculator_repl()

    output = capsys.readouterr().out
    assert "History loaded successfully" in output


def test_load_error(capsys):
    with patch('builtins.input', side_effect=['load', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.load_history',
               side_effect=Exception("file not found")):
        calculator_repl()

    output = capsys.readouterr().out
    assert "Error loading history: file not found" in output

def test_cancel_first_number(capsys):
    with patch('builtins.input', side_effect=['add', 'cancel', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()
    assert "Operation cancelled" in capsys.readouterr().out


def test_cancel_second_number(capsys):
    with patch('builtins.input', side_effect=['add', '2', 'cancel', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()
    assert "Operation cancelled" in capsys.readouterr().out


def test_validation_error(capsys):
    with patch('builtins.input', side_effect=['add', 'abc', '2', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.perform_operation',
               side_effect=ValidationError("bad input")):
        calculator_repl()
    assert "Error: bad input" in capsys.readouterr().out


def test_unexpected_error_in_operation(capsys):
    with patch('builtins.input', side_effect=['add', '2', '3', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.perform_operation',
               side_effect=RuntimeError("boom")):
        calculator_repl()
    assert "Unexpected error: boom" in capsys.readouterr().out


def test_unknown_command(capsys):
    with patch('builtins.input', side_effect=['foo', 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()
    assert "Unknown command: 'foo'" in capsys.readouterr().out


def test_keyboard_interrupt(capsys):
    with patch('builtins.input', side_effect=[KeyboardInterrupt, 'exit']), \
         patch('app.calculator.Calculator.save_history'):
        calculator_repl()
    assert "Operation cancelled" in capsys.readouterr().out


def test_eof_error(capsys):
    with patch('builtins.input', side_effect=EOFError):
        calculator_repl()
    assert "Input terminated. Exiting..." in capsys.readouterr().out


def test_fatal_error_on_init():
    import pytest
    with patch('app.calculator_repl.Calculator', side_effect=Exception("init failed")):
        with pytest.raises(Exception, match="init failed"):
            calculator_repl()

def test_loop_level_exception(capsys):
    with patch('builtins.input', side_effect=['history', 'exit']), \
         patch('app.calculator.Calculator.save_history'), \
         patch('app.calculator.Calculator.show_history',
               side_effect=Exception("history broke")):
        calculator_repl()
    assert "Error: history broke" in capsys.readouterr().out