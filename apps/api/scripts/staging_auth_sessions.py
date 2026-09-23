"""Validate Dayfold's Staging multi-device and refresh-token controls.

The script never prints or persists credentials. Supply two independent device
sessions through environment variables, then run one phase at a time around
the separately operated account-deletion control flow.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx


Phase = Literal["baseline", "blocked", "deleted"]
DENIED_STATUSES = {401, 403, 404}


def is_refresh_denied(status_code: int | None) -> bool:
    return status_code is not None and 400 <= status_code < 500


@dataclass(frozen=True)
class ProbeConfig:
    environment_id: str
    protected_url: str
    client_id: str | None = None
    client_secret: str | None = None
    timeout_seconds: float = 5.0

    @property
    def auth_base_url(self) -> str:
        return (
            f"https://{self.environment_id}.api.tcloudbasegateway.com/auth/v2"
        )

    @property
    def effective_client_id(self) -> str:
        return self.client_id or self.environment_id


@dataclass(frozen=True)
class DeviceCredentials:
    label: str
    access_token: str
    refresh_token: str


class StagingSessionVerifier:
    def __init__(
        self,
        config: ProbeConfig,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport

    def run(
        self,
        phase: Phase,
        devices: tuple[DeviceCredentials, DeviceCredentials],
    ) -> dict[str, Any]:
        if len({device.label for device in devices}) != 2:
            raise ValueError("Two uniquely labelled devices are required")
        if len({device.access_token for device in devices}) != 2 or len(
            {device.refresh_token for device in devices}
        ) != 2:
            raise ValueError("Two independent device sessions are required")

        with httpx.Client(
            timeout=self._config.timeout_seconds,
            transport=self._transport,
            follow_redirects=False,
        ) as client:
            results = [
                self._check_device(client, phase, device) for device in devices
            ]

        subjects = [result.pop("_subject") for result in results]
        subject_match = (
            phase != "baseline"
            or all(subjects)
            and len(set(subjects)) == 1
        )
        refresh_contract = None
        if phase == "baseline":
            valid_refresh_count = sum(
                result["refresh_valid"] for result in results
            )
            denied_refresh_count = sum(
                result["refresh_denied"] for result in results
            )
            if valid_refresh_count == len(results):
                refresh_contract = "multi_device"
            elif (
                valid_refresh_count == 1
                and denied_refresh_count == len(results) - 1
            ):
                refresh_contract = "latest_session_only"
            else:
                refresh_contract = "invalid"

        passed = (
            subject_match
            and all(result["passed"] for result in results)
            and refresh_contract != "invalid"
        )
        return {
            "phase": phase,
            "passed": passed,
            "subject_match": subject_match if phase == "baseline" else None,
            "refresh_contract": refresh_contract,
            "devices": results,
        }

    def _check_device(
        self,
        client: httpx.Client,
        phase: Phase,
        device: DeviceCredentials,
    ) -> dict[str, Any]:
        try:
            old_identity_status, old_subject = self._user_me(
                client, device.access_token
            )
            old_dayfold_status = self._dayfold_probe(
                client, device.access_token
            )
            refresh_status, refreshed_token = self._refresh(
                client, device.refresh_token
            )

            refreshed_identity_status = None
            refreshed_subject = None
            refreshed_dayfold_status = None
            if refreshed_token:
                refreshed_identity_status, refreshed_subject = self._user_me(
                    client, refreshed_token
                )
                refreshed_dayfold_status = self._dayfold_probe(
                    client, refreshed_token
                )

            refresh_valid = (
                refresh_status == 200
                and refreshed_identity_status == 200
                and refreshed_dayfold_status == 200
                and old_subject == refreshed_subject
            )
            if phase == "baseline":
                old_access_valid = (
                    old_identity_status == 200
                    and old_dayfold_status == 200
                )
                passed = old_access_valid and (
                    refresh_valid or is_refresh_denied(refresh_status)
                )
            else:
                old_access_denied = (
                    old_identity_status in DENIED_STATUSES
                    and old_dayfold_status in DENIED_STATUSES
                )
                refresh_denied = is_refresh_denied(refresh_status)
                refreshed_access_denied = (
                    refreshed_token is not None
                    and refreshed_dayfold_status in DENIED_STATUSES
                )
                passed = old_access_denied and (
                    refresh_denied or refreshed_access_denied
                )

            return {
                "label": device.label,
                "passed": passed,
                "old_identity_status": old_identity_status,
                "old_dayfold_status": old_dayfold_status,
                "old_access_denied": (
                    old_identity_status in DENIED_STATUSES
                    and old_dayfold_status in DENIED_STATUSES
                ),
                "refresh_status": refresh_status,
                "refresh_denied": is_refresh_denied(refresh_status),
                "refresh_valid": refresh_valid,
                "refreshed_identity_status": refreshed_identity_status,
                "refreshed_dayfold_status": refreshed_dayfold_status,
                "refreshed_access_denied": (
                    refreshed_token is not None
                    and refreshed_dayfold_status in DENIED_STATUSES
                ),
                "network_error": None,
                "_subject": old_subject,
            }
        except httpx.HTTPError as error:
            return {
                "label": device.label,
                "passed": False,
                "old_identity_status": None,
                "old_dayfold_status": None,
                "old_access_denied": False,
                "refresh_status": None,
                "refresh_denied": False,
                "refresh_valid": False,
                "refreshed_identity_status": None,
                "refreshed_dayfold_status": None,
                "refreshed_access_denied": False,
                "network_error": type(error).__name__,
                "_subject": None,
            }

    def _user_me(
        self,
        client: httpx.Client,
        access_token: str,
    ) -> tuple[int, str | None]:
        response = client.get(
            f"{self._config.auth_base_url}/user/me",
            params={"with_datasource": "false"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        subject = None
        if response.status_code == 200:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if isinstance(payload, dict) and isinstance(payload.get("sub"), str):
                subject = payload["sub"]
        return response.status_code, subject

    def _refresh(
        self,
        client: httpx.Client,
        refresh_token: str,
    ) -> tuple[int, str | None]:
        payload = {
            "client_id": self._config.effective_client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if self._config.client_secret:
            payload["client_secret"] = self._config.client_secret

        response = client.post(
            f"{self._config.auth_base_url}/token",
            json=payload,
        )
        refreshed_token = None
        if response.status_code == 200:
            try:
                response_payload = response.json()
            except ValueError:
                response_payload = {}
            if isinstance(response_payload, dict) and isinstance(
                response_payload.get("access_token"), str
            ):
                refreshed_token = response_payload["access_token"]
        return response.status_code, refreshed_token

    def _dayfold_probe(
        self,
        client: httpx.Client,
        access_token: str,
    ) -> int:
        response = client.get(
            self._config.protected_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return response.status_code


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_from_environment() -> tuple[
    ProbeConfig,
    tuple[DeviceCredentials, DeviceCredentials],
]:
    config = ProbeConfig(
        environment_id=_required_env("DAYFOLD_CLOUDBASE_ENV_ID"),
        protected_url=_required_env("DAYFOLD_STAGING_PROTECTED_URL"),
        client_id=os.getenv("DAYFOLD_CLOUDBASE_CLIENT_ID"),
        client_secret=os.getenv("DAYFOLD_CLOUDBASE_CLIENT_SECRET"),
        timeout_seconds=float(os.getenv("DAYFOLD_AUTH_PROBE_TIMEOUT", "5")),
    )
    devices = (
        DeviceCredentials(
            label="device_a",
            access_token=_required_env("DAYFOLD_DEVICE_A_ACCESS_TOKEN"),
            refresh_token=_required_env("DAYFOLD_DEVICE_A_REFRESH_TOKEN"),
        ),
        DeviceCredentials(
            label="device_b",
            access_token=_required_env("DAYFOLD_DEVICE_B_ACCESS_TOKEN"),
            refresh_token=_required_env("DAYFOLD_DEVICE_B_REFRESH_TOKEN"),
        ),
    )
    return config, devices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate two-device AccessToken and RefreshToken behavior without "
            "printing or persisting credentials."
        )
    )
    parser.add_argument(
        "phase",
        choices=("baseline", "blocked", "deleted"),
        help="Lifecycle phase that has already been established externally.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the sanitized JSON result.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        config, device_sessions = load_from_environment()
        result = StagingSessionVerifier(config).run(args.phase, device_sessions)
    except (ValueError, httpx.HTTPError) as error:
        result = {
            "phase": args.phase,
            "passed": False,
            "configuration_error": str(error),
        }

    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(f"{serialized}\n", encoding="utf-8")
    print(serialized)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
