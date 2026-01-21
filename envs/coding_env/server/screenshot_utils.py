# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Screenshot capture utilities for headless Xvfb display."""

import base64
import logging
import subprocess
import tempfile
import traceback
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def capture_screenshot_base64(display: str = ":99", verbose: bool = True) -> tuple[Optional[str], list[str]]:
    """
    Capture single screenshot from Xvfb display and return as base64-encoded PNG.

    Args:
        display: X11 display to capture (default :99)
        verbose: If True, collect debug information

    Returns:
        Tuple of (base64_string or None, list of debug messages)

    Uses ImageMagick's 'import' command to capture the display.
    """
    tmp_path = None
    debug_messages = []

    if verbose:
        debug_messages.append(f"[DEBUG] screenshot_utils: Starting screenshot capture for display {display}")

    try:
        # Create temporary file for screenshot
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = tmp_file.name

        if verbose:
            debug_messages.append(f"[DEBUG] screenshot_utils: Temporary file created: {tmp_path}")

        # Capture screenshot using ImageMagick import command
        # -window root = capture entire display
        # -display :99 = specify which X11 display
        cmd = ['import', '-window', 'root', '-display', display, tmp_path]

        if verbose:
            debug_messages.append(f"[DEBUG] screenshot_utils: Running command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=5,
            check=True
        )

        if verbose:
            debug_messages.append(f"[DEBUG] screenshot_utils: Command completed successfully")
            if result.stdout:
                debug_messages.append(f"[DEBUG] screenshot_utils: stdout: {result.stdout.decode()}")
            if result.stderr:
                debug_messages.append(f"[DEBUG] screenshot_utils: stderr: {result.stderr.decode()}")

        # Check if file was created and has content
        if not Path(tmp_path).exists():
            error_msg = "Screenshot file was not created"
            if verbose:
                debug_messages.append(f"[DEBUG] screenshot_utils: ERROR: {error_msg}")
            logger.error(error_msg)
            return None, debug_messages

        file_size = Path(tmp_path).stat().st_size
        if verbose:
            debug_messages.append(f"[DEBUG] screenshot_utils: Screenshot file size: {file_size} bytes")

        if file_size == 0:
            error_msg = "Screenshot file is empty"
            if verbose:
                debug_messages.append(f"[DEBUG] screenshot_utils: ERROR: {error_msg}")
            logger.error(error_msg)
            return None, debug_messages

        # Read PNG file and encode to base64
        with open(tmp_path, 'rb') as f:
            png_bytes = f.read()
            base64_str = base64.b64encode(png_bytes).decode('utf-8')

        if verbose:
            debug_messages.append(f"[DEBUG] screenshot_utils: Screenshot captured: {len(png_bytes)} bytes PNG, {len(base64_str)} bytes base64")

        logger.debug(f"Screenshot captured: {len(png_bytes)} bytes PNG, {len(base64_str)} bytes base64")
        return base64_str, debug_messages

    except subprocess.TimeoutExpired:
        error_msg = "Screenshot capture timed out"
        if verbose:
            debug_messages.append(f"[DEBUG] screenshot_utils: ERROR: {error_msg}")
        logger.error(error_msg)
        return None, debug_messages
    except subprocess.CalledProcessError as e:
        stdout = e.stdout.decode() if e.stdout else "No stdout"
        stderr = e.stderr.decode() if e.stderr else "No stderr"
        error_msg = f"Screenshot capture failed with exit code {e.returncode}"
        if verbose:
            debug_messages.append(f"[DEBUG] screenshot_utils: ERROR: {error_msg}")
            debug_messages.append(f"[DEBUG] screenshot_utils: stdout: {stdout}")
            debug_messages.append(f"[DEBUG] screenshot_utils: stderr: {stderr}")
        logger.error(f"{error_msg}\nstdout: {stdout}\nstderr: {stderr}")
        return None, debug_messages
    except FileNotFoundError as e:
        error_msg = f"Command not found: {e}"
        if verbose:
            debug_messages.append(f"[DEBUG] screenshot_utils: ERROR: {error_msg}")
            debug_messages.append(f"[DEBUG] screenshot_utils: Make sure ImageMagick 'import' command is installed")
        logger.error(error_msg)
        return None, debug_messages
    except Exception as e:
        error_msg = f"Unexpected error capturing screenshot: {e}"
        if verbose:
            debug_messages.append(f"[DEBUG] screenshot_utils: ERROR: {error_msg}")
            debug_messages.append(f"[DEBUG] screenshot_utils: Traceback: {traceback.format_exc()}")
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return None, debug_messages
    finally:
        # Ensure cleanup even if error occurred
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
                if verbose:
                    debug_messages.append(f"[DEBUG] screenshot_utils: Cleaned up temporary file: {tmp_path}")
            except Exception as e:
                if verbose:
                    debug_messages.append(f"[DEBUG] screenshot_utils: WARNING: Failed to cleanup {tmp_path}: {e}")
