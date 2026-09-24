"""Student voice STT schemas — T-155."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceTranscribeRead(BaseModel):
    """faster-whisper transcript for a student voice clip (T-155)."""

    transcript: str = Field(min_length=0)
