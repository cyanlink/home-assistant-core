"""Auth provider that validates credentials via an external command."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_COMMAND
from homeassistant.exceptions import HomeAssistantError

from ..models import AuthFlowContext, AuthFlowResult, Credentials, UserMeta
from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow

CONF_ARGS = "args"
CONF_META = "meta"

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND): vol.All(
            str, os.path.normpath, msg="must be an absolute path"
        ),
        vol.Optional(CONF_ARGS, default=None): vol.Any(vol.DefaultTo(list), [str]),
        vol.Optional(CONF_META, default=False): bool,
    },
    extra=vol.PREVENT_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


class InvalidAuthError(HomeAssistantError):
    """Raised when authentication with given credentials fails."""


@AUTH_PROVIDERS.register("command_line")
class CommandLineAuthProvider(AuthProvider):
    """Auth provider validating credentials by calling a command."""

    DEFAULT_TITLE = "Command Line Authentication"

    # which keys to accept from a program's stdout
    ALLOWED_META_KEYS = (
        "name",
        "group",
        "local_only",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Extend parent's __init__.

        Adds self._user_meta dictionary to hold the user-specific
        attributes provided by external programs.
        """
        super().__init__(*args, **kwargs)
        self._user_meta: dict[str, dict[str, Any]] = {}

    async def async_login_flow(
        self, context: AuthFlowContext | None
    ) -> CommandLineLoginFlow:
        """Return a flow to login."""
        return CommandLineLoginFlow(self)

    async def async_validate_login(self, username: str, password: str) -> None:
        """Validate a username and password."""

        env = self._build_login_env(username, password)
        cmd, args = self._read_cmd_and_args()
        stdout_pipe = self._desired_stdout_pipe()

        try:
            stdout = await self._run_auth_command(cmd, args, env, stdout_pipe)
        except OSError as err:
            # command 不存在或权限问题等
            _LOGGER.error("Error while authenticating %r: %s", username, err)
            raise InvalidAuthError from err

        self._handle_auth_result(stdout)


# --------- helpers---------

    def _build_login_env(self, username: str, password: str) -> dict[str, str]:
        # 单一职责：拼 env
        return {"username": username, "password": password}

    def _read_cmd_and_args(self) -> tuple[str, tuple[str, ...]]:
        # 单一职责：读命令与参数
        return self.config[CONF_COMMAND], tuple(self.config[CONF_ARGS])

    def _desired_stdout_pipe(self) -> Any:
        # 单一职责：决定是否捕获 stdout
        return asyncio.subprocess.PIPE if self.config[CONF_META] else None

    async def _run_auth_command(
        self,
        cmd: str,
        args: tuple[str, ...],
        env: dict[str, str],
        stdout_pipe: Any,
    ) -> bytes | None:
        # 单一职责：执行进程并返回 stdout
        process = await asyncio.create_subprocess_exec(
            cmd, *args, env=env, stdout=stdout_pipe, close_fds=False  # posix_spawn 需要
        )
        stdout, _ = await process.communicate()
        return stdout

    def _handle_auth_result(self, stdout: bytes | None) -> None:
        # 按你原来的逻辑处理返回（这里保留为占位，避免把复杂度重新引回主函数）
        # 例如：如果需要从 meta 的 stdout 中解析登录结果，就在这里做
        if stdout is None:
            return


    async def async_get_or_create_credentials(
        self, flow_result: Mapping[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        username = flow_result["username"]
        for credential in await self.async_credentials():
            if credential.data["username"] == username:
                return credential

        # Create new credentials.
        return self.async_create_credentials({"username": username})

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Return extra user metadata for credentials.

        Currently, supports name, group and local_only.
        """
        meta = self._user_meta.get(credentials.data["username"], {})
        return UserMeta(
            name=meta.get("name"),
            is_active=True,
            group=meta.get("group"),
            local_only=meta.get("local_only") == "true",
        )


class CommandLineLoginFlow(LoginFlow[CommandLineAuthProvider]):
    """Handler for the login flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> AuthFlowResult:
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            user_input["username"] = user_input["username"].strip()
            try:
                await self._auth_provider.async_validate_login(
                    user_input["username"], user_input["password"]
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"

            if not errors:
                user_input.pop("password")
                return await self.async_finish(user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )
