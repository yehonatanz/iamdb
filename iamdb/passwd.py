from typing import Optional

import keyring


class CouldNotResolvePassword(Exception):
    pass


def resolve_password(
    user: str,
    password: Optional[str] = None,
    force_password_prompt: bool = False,
    no_password_prompt: bool = True,
) -> str:
    """
    Resolves the password for user.
    If password is given -> returns password.
    Else, tries keyring and prompt according to flags.
    Does not save the resolved password.
    """
    if force_password_prompt and no_password_prompt:
        raise ValueError(
            "Cannot specify bot force_password_prompt and no_password_prompt!"
        )
    elif force_password_prompt:
        password = _prompt_for_password(user)
    else:
        password = password or load(user)
        if not no_password_prompt:
            password = password or _prompt_for_password(user)

    if not password:
        raise CouldNotResolvePassword(f"Could not resolve password for {user}")
    return password


def _prompt_for_password(user: str) -> str:
    import click

    return click.prompt(f"Password for {user}", hide_input=True)


def load(user: str) -> str:
    """
    Loads the iamdb password for user via keyring
    """
    return keyring.get_password("iamdb", user)


def save(user: str, password: str):
    """
    Stores the iamdb password for user via keyring
    """
    keyring.set_password("iamdb", user, password)
