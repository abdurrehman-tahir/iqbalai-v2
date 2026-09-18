"""Voice (STT/TTS) abstraction — T-121, STACK_LOCK §4.4.

The only package allowed to import ``faster_whisper``, ``piper``, or
``edge_tts`` (stack-enforcer Rule 2 / CLAUDE.md "No bypassing the voice
abstraction"). Everything else calls into ``router.py``.
"""

from __future__ import annotations
