"""
Progress indicator utilities for EKS NVIDIA Tools CLI
"""

import sys
import time
from typing import Optional, Any
from contextlib import contextmanager


class ProgressIndicator:
    """Simple progress indicator for CLI operations."""
    
    def __init__(self, message: str, enabled: bool = True):
        """
        Initialize progress indicator.
        
        Args:
            message: Message to display during progress
            enabled: Whether to show progress (disabled in quiet mode)
        """
        self.message = message
        self.enabled = enabled
        self.start_time: Optional[float] = None
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_index = 0
    
    def start(self) -> None:
        """Start the progress indicator."""
        if not self.enabled:
            return
        
        self.start_time = time.time()
        sys.stdout.write(f"{self.message}... ")
        sys.stdout.flush()
    
    def update(self, new_message: Optional[str] = None) -> None:
        """Update the progress indicator with a new message."""
        if not self.enabled:
            return
        
        if new_message:
            self.message = new_message
            sys.stdout.write(f"\r{self.message}... ")
            sys.stdout.flush()
    
    def spin(self) -> None:
        """Show a spinner character."""
        if not self.enabled:
            return
        
        char = self.spinner_chars[self.spinner_index]
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
        sys.stdout.write(f"\r{char} {self.message}... ")
        sys.stdout.flush()
    
    def finish(self, success: bool = True, final_message: Optional[str] = None) -> None:
        """Finish the progress indicator."""
        if not self.enabled:
            return
        
        if self.start_time:
            elapsed = time.time() - self.start_time
            elapsed_str = f" ({elapsed:.1f}s)"
        else:
            elapsed_str = ""
        
        if final_message:
            message = final_message
        else:
            message = "✓ Done" if success else "✗ Failed"
        
        sys.stdout.write(f"\r{message}{elapsed_str}\n")
        sys.stdout.flush()


@contextmanager
def progress(message: str, enabled: bool = True):
    """
    Context manager for showing progress during an operation.
    
    Args:
        message: Message to display during progress
        enabled: Whether to show progress (disabled in quiet mode)
    
    Yields:
        ProgressIndicator instance
    """
    indicator = ProgressIndicator(message, enabled)
    indicator.start()
    
    try:
        yield indicator
        indicator.finish(success=True)
    except Exception:
        indicator.finish(success=False)
        raise


def print_step(step_number: int, total_steps: int, message: str, enabled: bool = True) -> None:
    """
    Print a numbered step in a multi-step process.
    
    Args:
        step_number: Current step number (1-based)
        total_steps: Total number of steps
        message: Step description
        enabled: Whether to print (disabled in quiet mode)
    """
    if not enabled:
        return
    
    print(f"Step {step_number}/{total_steps}: {message}")


def print_separator(title: Optional[str] = None, enabled: bool = True) -> None:
    """
    Print a section separator.
    
    Args:
        title: Optional section title
        enabled: Whether to print (disabled in quiet mode)
    """
    if not enabled:
        return
    
    if title:
        width = 60
        padding = (width - len(title) - 2) // 2
        print("=" * padding + f" {title} " + "=" * padding)
    else:
        print("=" * 60)