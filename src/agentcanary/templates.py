"""Nonfunctional built-ins and bounded, nonexecutable text templates."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from string import Template
from uuid import uuid4

from .models import TOKEN_PREFIX, Canary

LABEL = "AGENTCANARY SYNTHETIC ONLY - NONFUNCTIONAL"
MAX_TEMPLATE_BYTES = 256 * 1024

BUILTINS: dict[str, str] = {
    "aws-key": "# $label\n[synthetic-demo]\naws_access_key_id = INVALID_$token\n"
    "aws_secret_access_key = INVALID_$token\n",
    "openai-key": "# $label\nOPENAI_API_KEY=INVALID_$token\n"
    "OPENAI_BASE_URL=https://api.openai.invalid/v1\n",
    "anthropic-key": "# $label\nANTHROPIC_API_KEY=INVALID_$token\n"
    "ANTHROPIC_BASE_URL=https://api.anthropic.invalid\n",
    "kubeconfig": "# $label\napiVersion: v1\nkind: Config\nclusters:\n"
    "  - name: synthetic\n    cluster:\n      server: https://cluster.invalid\n"
    "users:\n  - name: synthetic\n    user:\n      token: INVALID_$token\n"
    "contexts:\n  - name: synthetic\n    context:\n      cluster: synthetic\n"
    "      user: synthetic\ncurrent-context: synthetic\n",
    "ssh-key": "# $label\n-----BEGIN AGENTCANARY NONFUNCTIONAL KEY-----\n"
    "$token\n-----END AGENTCANARY NONFUNCTIONAL KEY-----\n",
    "env": "# $label\nAPP_ENV=synthetic-test\nAPP_SECRET=INVALID_$token\n"
    "API_URL=https://service.invalid\n",
    "database": "# $label\nDATABASE_URL=postgresql://synthetic:INVALID_$token"
    "@database.invalid:5432/synthetic\n",
    "payroll": "# $label\nemployee_id,employee_name,account_reference,amount_usd\n"
    "SYNTHETIC-001,SYNTHETIC PERSON,INVALID_$token,0.00\n",
}


@dataclass(frozen=True, slots=True)
class GeneratedCanary:
    canary: Canary
    content: str


def generate(kind: str, path: str, *, template: str | None = None) -> GeneratedCanary:
    """Generate in memory; does not write or register anything."""
    if template is None:
        if kind not in BUILTINS:
            raise ValueError("unknown canary type")
        template = BUILTINS[kind]
    elif kind != "custom":
        raise ValueError("custom template requires kind='custom'")
    if len(template.encode("utf-8")) > MAX_TEMPLATE_BYTES:
        raise ValueError("template exceeds 256 KiB")
    if "\x00" in template:
        raise ValueError("template must be plain text without NUL bytes")
    identifier = str(uuid4())
    token = TOKEN_PREFIX + secrets.token_hex(16)
    try:
        content = Template(template).substitute(token=token, canary_id=identifier, label=LABEL)
    except (KeyError, ValueError) as exc:
        raise ValueError(
            "template supports only $token, $canary_id and $label; escape $ as $$"
        ) from exc
    if token not in content:
        raise ValueError("custom template must include $token")
    if LABEL not in content:
        content = f"# {LABEL}\n{content}"
    if len(content.encode("utf-8")) > MAX_TEMPLATE_BYTES:
        raise ValueError("rendered artifact exceeds 256 KiB")
    canary = Canary(
        id=identifier,
        kind=kind,
        token=token,
        path=path,
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
    return GeneratedCanary(canary, content)
