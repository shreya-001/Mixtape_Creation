from __future__ import annotations

import streamlit as st


st.set_page_config(page_title="Google Auth Login", layout="centered")


def login_screen() -> None:
    """Prompt the user to log in with Google via Streamlit's auth."""
    st.header("This app is private.")
    st.subheader("Please log in.")
    st.button("Log in with Google", on_click=st.login)


def main() -> None:
    # If the user is not logged in, show the login screen.
    if not st.user.is_logged_in:  # type: ignore[attr-defined]
        login_screen()
        return

    # Once logged in, greet the user and offer a logout button.
    st.header(f"Welcome, {st.user.name}!")  # type: ignore[attr-defined]
    st.button("Log out", on_click=st.logout)


if __name__ == "__main__":
    main()


