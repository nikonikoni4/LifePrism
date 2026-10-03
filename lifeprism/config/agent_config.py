"""Typed Agent configuration persisted under config.yaml's agent section."""

from pathlib import Path, PurePosixPath, PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class LLMRetrySettings(_ConfigModel):
    """Loop-managed retry switch and exponential backoff parameters."""

    enabled: bool = True
    base_delay: float = Field(default=1.0, ge=0)
    multiplier: float = Field(default=2.0, ge=1)
    cap: float = Field(default=30.0, ge=0)

    def backoff_policy(self) -> dict[str, float]:
        """Return parameters accepted by the native loop's RetryPolicy."""
        return self.model_dump(exclude={"enabled"})


class ToolGuardSettings(_ConfigModel):
    """Allow-list paths; relative entries use the LifePrism data directory."""

    allow_paths: list[str] = Field(default_factory=lambda: ["user", "diary", "agent"])

    @model_validator(mode="before")
    @classmethod
    def discard_legacy_switch(cls, value):
        """Ignore the retired enabled switch; guard registration is mandatory."""
        if isinstance(value, dict):
            return {key: item for key, item in value.items() if key != "enabled"}
        return value

    @field_validator("allow_paths")
    @classmethod
    def validate_paths(cls, paths: list[str]) -> list[str]:
        for raw in paths:
            if not raw.strip():
                raise ValueError("allow_paths entries cannot be empty")
            # Portable relative paths use forward slashes, never parent traversal.
            if not (PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute()) and (
                PureWindowsPath(raw).drive or "\\" in raw or ".." in PurePosixPath(raw).parts
            ):
                raise ValueError(
                    "relative allow_paths must use forward slashes without parent traversal"
                )
        return paths

    def resolve_paths(self, data_path: Path) -> list[str]:
        """Resolve portable entries; reject foreign absolute paths on this host."""
        root = data_path.resolve()
        result = []
        for raw in self.allow_paths:
            path = Path(raw)
            if PureWindowsPath(raw).is_absolute() or PurePosixPath(raw).is_absolute():
                if not path.is_absolute():
                    raise ValueError(f"allow_path is not absolute on this platform: {raw}")
                resolved = path.resolve()
            else:
                resolved = (root / path).resolve()
                if not resolved.is_relative_to(root):
                    raise ValueError(f"allow_path escapes data directory: {raw}")
            result.append(str(resolved))
        return result


class AgentPolicySettings(_ConfigModel):
    llm_retry: LLMRetrySettings = Field(default_factory=LLMRetrySettings)
    tool_guard: ToolGuardSettings = Field(default_factory=ToolGuardSettings)


class AgentSettings(_ConfigModel):
    """Snapshot loaded when an AgentContext is created; saves go through settings."""

    step_limit: int = Field(default=20, ge=1)
    max_retry_count: int = Field(default=3, ge=0)
    policies: AgentPolicySettings = Field(default_factory=AgentPolicySettings)
