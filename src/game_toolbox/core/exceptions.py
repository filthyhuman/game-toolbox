"""Exception hierarchy for the game-toolbox framework."""


class ToolboxError(Exception):
    """Base exception for all game-toolbox errors."""


class ToolError(ToolboxError):
    """Raised when a tool encounters an error during execution."""


class ValidationError(ToolboxError):
    """Raised when parameter validation fails."""


class PipelineError(ToolboxError):
    """Raised when a pipeline encounters an error."""
