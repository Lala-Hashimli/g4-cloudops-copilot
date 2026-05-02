from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class SSHResult:
    host: str
    command: str
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SafeSSHClient:
    def __init__(self, ssh_user: str, ssh_key_path: str) -> None:
        self.ssh_user = ssh_user
        self.ssh_key_path = ssh_key_path

    async def run_ssh(self, host: str, command: str, timeout: int = 15) -> SSHResult:
        ssh_command = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            self.ssh_key_path,
            f"{self.ssh_user}@{host}",
            command,
        ]

        logger.info("Running SSH check on %s", host)
        process = await asyncio.create_subprocess_exec(
            *ssh_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return SSHResult(
                host=host,
                command=command,
                return_code=124,
                stdout="",
                stderr=f"Timed out after {timeout}s",
                timed_out=True,
            )

        return SSHResult(
            host=host,
            command=command,
            return_code=process.returncode,
            stdout=stdout.decode("utf-8", errors="replace").strip(),
            stderr=stderr.decode("utf-8", errors="replace").strip(),
        )
