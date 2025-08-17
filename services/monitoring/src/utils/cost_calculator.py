"""Cost calculation utilities for different LLM models."""

from decimal import Decimal
from typing import Union

# Cost per 1K tokens (in USD)
MODEL_COSTS = {
    # OpenAI Models
    "gpt-4": {
        "input": 0.03,
        "output": 0.06
    },
    "gpt-4-32k": {
        "input": 0.06,
        "output": 0.12
    },
    "gpt-3.5-turbo": {
        "input": 0.0015,
        "output": 0.002
    },
    "gpt-3.5-turbo-16k": {
        "input": 0.003,
        "output": 0.004
    },
    # Claude Models (Anthropic)
    "claude-3-opus": {
        "input": 0.015,
        "output": 0.075
    },
    "claude-3-sonnet": {
        "input": 0.003,
        "output": 0.015
    },
    "claude-3-haiku": {
        "input": 0.00025,
        "output": 0.00125
    },
    "claude-2.1": {
        "input": 0.008,
        "output": 0.024
    },
    # Default fallback
    "default": {
        "input": 0.002,
        "output": 0.002
    }
}


def calculate_cost(
    model: str,
    input_tokens: Union[int, float],
    output_tokens: Union[int, float]
) -> float:
    """
    Calculate the cost of an LLM API call based on token usage.
    
    Args:
        model: The model name (e.g., "gpt-3.5-turbo")
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens
    
    Returns:
        Total cost in USD
    """
    # Get model costs or use default
    costs = MODEL_COSTS.get(model, MODEL_COSTS["default"])
    
    # Calculate costs (prices are per 1K tokens)
    input_cost = (input_tokens / 1000) * costs["input"]
    output_cost = (output_tokens / 1000) * costs["output"]
    
    total_cost = input_cost + output_cost
    
    # Round to 6 decimal places for precision
    return round(total_cost, 6)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from text.
    Rule of thumb: 1 token ≈ 4 characters or 0.75 words
    
    Args:
        text: The text to estimate tokens for
    
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Use character count method (more accurate for code/technical content)
    char_estimate = len(text) / 4
    
    # Use word count method
    word_estimate = len(text.split()) * 1.33
    
    # Return average of both methods
    return int((char_estimate + word_estimate) / 2)


def get_model_info(model: str) -> dict:
    """
    Get information about a model including costs and limits.
    
    Args:
        model: The model name
    
    Returns:
        Dictionary with model information
    """
    costs = MODEL_COSTS.get(model, MODEL_COSTS["default"])
    
    # Model context limits (in tokens)
    context_limits = {
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
        "gpt-3.5-turbo": 4096,
        "gpt-3.5-turbo-16k": 16384,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        "claude-2.1": 200000,
    }
    
    return {
        "model": model,
        "input_cost_per_1k": costs["input"],
        "output_cost_per_1k": costs["output"],
        "context_limit": context_limits.get(model, 4096),
        "provider": _get_provider(model)
    }


def _get_provider(model: str) -> str:
    """Get provider name from model name."""
    if "gpt" in model.lower():
        return "openai"
    elif "claude" in model.lower():
        return "anthropic"
    elif "llama" in model.lower():
        return "meta"
    else:
        return "unknown"


def calculate_monthly_projection(
    daily_cost: float,
    growth_rate: float = 1.0
) -> float:
    """
    Project monthly costs based on daily usage.
    
    Args:
        daily_cost: Current daily cost
        growth_rate: Expected growth multiplier (1.0 = no growth)
    
    Returns:
        Projected monthly cost
    """
    return daily_cost * 30 * growth_rate