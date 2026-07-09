"""
Password-gated RBAC elevation for Streamlit.

Default access is always Viewer. Elevated roles require a password. Resolution
order: Streamlit Secrets, environment variables, then demo defaults below
(local and Streamlit Cloud). Set Secrets to override defaults on deploy.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Literal

import streamlit as st

ElevatedRole = Literal["clinician", "analyst"]

SESSION_ELEVATED = "rbac_elevated_role"
SESSION_PROOF = "rbac_auth_proof"
SESSION_FAILS = "rbac_auth_fail_count"
SESSION_LOCK_UNTIL = "rbac_auth_lock_until"

ROLE_RANK = {"viewer": 0, "clinician": 1, "analyst": 2, "admin": 3}

# Max failed attempts before a short lockout (anti brute-force in-session).
MAX_FAILS = 5
LOCKOUT_SECONDS = 120
PROOF_TTL_SECONDS = 8 * 3600

DEFAULT_CLINICIAN_PASSWORD = "baguvix"
DEFAULT_ANALYST_PASSWORD = "aezakmi"


def _password_for(role: ElevatedRole) -> str:
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            if role == "clinician" and "RBAC_CLINICIAN_PASSWORD" in st.secrets:
                return str(st.secrets["RBAC_CLINICIAN_PASSWORD"])
            if role == "analyst" and "RBAC_ANALYST_PASSWORD" in st.secrets:
                return str(st.secrets["RBAC_ANALYST_PASSWORD"])
    except Exception:
        pass

    env_key = "RBAC_CLINICIAN_PASSWORD" if role == "clinician" else "RBAC_ANALYST_PASSWORD"
    env_val = os.environ.get(env_key, "").strip()
    if env_val:
        return env_val

    return DEFAULT_CLINICIAN_PASSWORD if role == "clinician" else DEFAULT_ANALYST_PASSWORD


def _auth_secret() -> bytes:
    try:
        import streamlit as st

        if hasattr(st, "secrets") and "RBAC_AUTH_SECRET" in st.secrets:
            return str(st.secrets["RBAC_AUTH_SECRET"]).encode("utf-8")
    except Exception:
        pass
    env = os.environ.get("RBAC_AUTH_SECRET", "").strip()
    if env:
        return env.encode("utf-8")
    if "_rbac_server_secret" not in st.session_state:
        st.session_state["_rbac_server_secret"] = secrets.token_hex(32)
    return st.session_state["_rbac_server_secret"].encode("utf-8")


def _sign_proof(role: str, expires_at: int) -> str:
    payload = f"{role}|{expires_at}"
    sig = hmac.new(_auth_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def _verify_proof(proof: str) -> str | None:
    try:
        role, expires_s, sig = proof.split("|", 2)
        expires_at = int(expires_s)
        if expires_at < int(time.time()):
            return None
        if role not in ROLE_RANK or role == "viewer":
            return None
        payload = f"{role}|{expires_at}"
        expected = hmac.new(_auth_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        return role
    except Exception:
        return None


def _is_locked_out() -> bool:
    until = float(st.session_state.get(SESSION_LOCK_UNTIL, 0) or 0)
    return time.time() < until


def get_effective_role() -> str:
    """
    Single source of truth for permissions.
    Never trust a role string passed from UI widgets.
    """
    proof = st.session_state.get(SESSION_PROOF)
    if not proof:
        return "viewer"
    verified = _verify_proof(str(proof))
    if not verified:
        lock_to_viewer(silent=True)
        return "viewer"
    st.session_state[SESSION_ELEVATED] = verified
    return verified


def lock_to_viewer(*, silent: bool = False) -> None:
    for key in (SESSION_ELEVATED, SESSION_PROOF, SESSION_FAILS, SESSION_LOCK_UNTIL):
        st.session_state.pop(key, None)
    for widget_key in (
        "rbac_unlock_password",
        "rbac_switch_analyst_pwd",
        "rbac_switch_clinician_pwd",
    ):
        st.session_state.pop(widget_key, None)
    if not silent:
        st.session_state.pop("last_scored_row", None)
        st.session_state.pop("selected_encounter_id", None)


def _apply_elevation(target: ElevatedRole) -> None:
    expires_at = int(time.time()) + PROOF_TTL_SECONDS
    proof = _sign_proof(target, expires_at)
    st.session_state[SESSION_ELEVATED] = target
    st.session_state[SESSION_PROOF] = proof
    st.session_state[SESSION_FAILS] = 0
    st.session_state.pop(SESSION_LOCK_UNTIL, None)


def downgrade_to_clinician() -> tuple[bool, str]:
    """Analyst → Clinician without password (downgrade only)."""
    if get_effective_role() != "analyst":
        return False, "Only Analyst sessions can switch down to Clinician."
    _apply_elevation("clinician")
    return True, "Switched to Clinician mode."


def authenticate_elevation(target: ElevatedRole, password: str) -> tuple[bool, str]:
    """
    Verify password and elevate session. Returns (ok, message).
    """
    if _is_locked_out():
        remaining = int(st.session_state.get(SESSION_LOCK_UNTIL, 0) - time.time())
        return False, f"Too many failed attempts. Try again in {max(remaining, 1)}s."

    expected = _password_for(target)
    if not expected:
        return False, (
            "RBAC passwords are not configured on this deployment. "
            "Set RBAC_CLINICIAN_PASSWORD and RBAC_ANALYST_PASSWORD in Streamlit Secrets."
        )
    supplied = (password or "").strip()
    if not supplied or len(supplied) != len(expected) or not hmac.compare_digest(supplied, expected):
        fails = int(st.session_state.get(SESSION_FAILS, 0) or 0) + 1
        st.session_state[SESSION_FAILS] = fails
        if fails >= MAX_FAILS:
            st.session_state[SESSION_LOCK_UNTIL] = time.time() + LOCKOUT_SECONDS
            st.session_state[SESSION_FAILS] = 0
            return False, f"Incorrect password. Locked for {LOCKOUT_SECONDS}s."
        return False, "Incorrect password."

    _apply_elevation(target)
    return True, f"Unlocked {target.title()} mode."


def validate_role(role: str | None) -> str:
    """
    Anti-tamper: ignore any role passed from callers; always return
    the server-verified effective role.
    """
    effective = get_effective_role()
    if role and role != effective:
        return effective
    return effective
