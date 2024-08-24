import pytest
from unittest.mock import AsyncMock, patch
from telegram import User
from bot import error_handler, set_commands


@pytest.mark.asyncio
async def test_start_command():
    # Mock the update and context objects
    mock_update = AsyncMock()
    mock_context = AsyncMock()

    # Mock user and message
    mock_user = User(id=12345, first_name="Test", is_bot=False)
    mock_update.effective_user = mock_user
    mock_update.message.text = "/start"

    # Patch the start function
    with patch("action_handlers.handlers.start") as mock_start:
        await mock_start(mock_update, mock_context)

        # Check if the start function was called
        mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_error_handler():
    # Mock the update and context objects
    mock_update = AsyncMock()
    mock_context = AsyncMock()
    mock_context.error = Exception("Test Exception")

    with patch("bot.logger") as mock_logger:
        await error_handler(mock_update, mock_context)

        # Check if the logger's error method was called once
        assert mock_logger.error.call_count == 1

        # Extract the actual arguments with which logger.error was called
        call_args, call_kwargs = mock_logger.error.call_args

        # Ensure the correct message and exception were logged
        assert "An error occurred while handling an update:" in call_kwargs["msg"]
        assert isinstance(call_kwargs["exc_info"], Exception)


@pytest.mark.asyncio
async def test_set_commands():
    # Mock the application object and its bot attribute
    mock_application = AsyncMock()
    mock_application.bot.set_my_commands = AsyncMock()

    await set_commands(mock_application)

    # Ensure that commands are set up
    assert mock_application.bot.set_my_commands.called
