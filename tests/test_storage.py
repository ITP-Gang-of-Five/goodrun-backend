from app.storage import get_users


def test_the_admin_exists() -> None:
    #Ensure that the admin account exists / is successfully created
    admin = get_users().get_by_email("admin")
    assert admin is not None
    assert admin.password == "admin"
    assert get_users().get_by_id(admin.id) == admin


def test_unknown_users_are_none() -> None:
    #Ensure that random users that don't exist just return None
    assert get_users().get_by_id(999) is None
    assert get_users().get_by_email("nobody") is None
    assert get_users().get_by_email("i am not real") is None
