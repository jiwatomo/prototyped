"""Static wiring checks for landing, login, profile, home and admin pages."""
from __future__ import annotations

from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def read(name: str) -> str:
    return (FRONTEND / name).read_text(encoding="utf-8")


def test_landing_routes_to_both_roles():
    landing = read("index.html")
    assert "login.html?role=user" in landing
    assert "login.html?role=admin" in landing
    assert "DATA DEMO SINTETIS" in landing
    assert "landing.js" in landing


def test_login_page_has_role_switch_and_demo_accounts():
    login = read("login.html")
    assert "js/auth.js" in login
    assert "js/login.js" in login
    assert "demo-student" in login and "demo-admin" in login
    assert 'id="login-error"' in login


def test_login_routes_students_to_profile_or_home_and_admins_to_admin():
    script = read("js/login.js")
    assert 'window.location.replace("admin.html")' in script
    assert "profile.html" in script
    assert "submitted" in script


def test_profile_page_is_a_dedicated_input_page():
    page = read("profile.html")
    assert 'id="description"' in page
    assert 'id="btn-analyze"' in page
    assert 'id="btn-confirm"' in page
    assert "satu kali" in page
    assert "js/profile.js" in page
    # Tags are internal: the review step must not render them.
    assert "suggested-tags" not in page


def test_profile_script_submits_once_then_redirects():
    script = read("js/profile.js")
    assert "submitted" in script
    assert 'window.location.replace("app.html")' in script
    assert "satu kali" in script


def test_home_page_shows_recommendations_and_no_mode_switcher():
    page = read("app.html")
    assert "js/home.js" in page
    assert 'id="rec-list"' in page
    assert "tab-user" not in page and "tab-admin" not in page
    assert "Pengguna</button>" not in page
    assert "js/auth.js" in page
    assert 'id="session-user"' in page
    # The submitted-profile section lives on its own URL now.
    assert 'id="facts-summary"' not in page
    assert "my-profile.html" in page


def test_profile_summary_has_a_dedicated_page():
    page = read("my-profile.html")
    for element in ["facts-summary", "fact-gpa", "btn-save-facts", "profile-description"]:
        assert f'id="{element}"' in page, element
    assert "js/my-profile.js" in page
    assert 'href="app.html"' in page

    script = read("js/my-profile.js")
    assert "updateProfile" in script
    assert 'window.location.replace("profile.html")' in script


def test_admin_dashboard_is_its_own_page():
    page = read("admin.html")
    assert 'data-page-role="admin"' in page
    assert "admin-dashboard.js" in page
    assert 'id="stat-users"' in page
    assert 'id="pending-list"' in page
    assert "admin-nav" in page
    assert "tab-user" not in page and "tab-admin" not in page


def test_admin_users_page_has_create_and_reset_controls():
    page = read("admin-users.html")
    for element in ["new-username", "new-password", "users-tbody", "reset-card", "btn-reset-password"]:
        assert f'id="{element}"' in page, element
    assert "admin-users.js" in page
    script = read("js/admin-users.js")
    assert "createAdminUser" in script
    assert "resetUserPassword" in script


def test_admin_new_scholarship_page_has_both_creation_paths():
    page = read("admin-new-scholarship.html")
    assert 'id="btn-extract"' in page
    assert 'id="manual-name"' in page
    assert "admin-new.js" in page and "admin-manual.js" in page
    script = read("js/admin-new.js")
    assert "admin-scholarships.html?id=" in script


def test_admin_scholarships_page_manages_catalogue():
    page = read("admin-scholarships.html")
    for element in ["filter-status", "filter-search", "scholarship-tbody", "sch-tags", "btn-approve-scholarship"]:
        assert f'id="{element}"' in page, element
    script = read("js/admin-scholarships.js")
    assert "approveAdminScholarship" in script
    assert "rejectAdminScholarship" in script
    assert "patchAdminScholarship" in script


def test_every_admin_page_guards_the_admin_role():
    for name in ["admin.html", "admin-users.html", "admin-scholarships.html", "admin-new-scholarship.html"]:
        page = read(name)
        assert 'data-page-role="admin"' in page, name
        assert "js/shell.js" in page, name


def test_api_client_attaches_bearer_token():
    api = read("js/api.js")
    assert "Authorization" in api
    assert "Bearer" in api
    assert api.count("await fetch(") == 1


def test_auth_module_stores_session_locally_and_clears_it():
    auth = read("js/auth.js")
    assert "sessionStorage" in auth
    assert "requireSession" in auth
    assert "logout" in auth


def test_admin_page_has_manual_entry_form():
    page = read("admin-new-scholarship.html")
    for element in [
        "manual-name",
        "manual-organizer",
        "manual-levels",
        "manual-benefits",
        "manual-start",
        "manual-deadline",
        "manual-description",
        "manual-tags",
        "manual-requirements",
        "btn-save-manual",
    ]:
        assert f'id="{element}"' in page, element
    assert "admin-manual.js" in page


def test_manual_form_posts_to_admin_endpoint():
    script = read("js/admin-manual.js")
    assert "createManualScholarship" in script
    assert "is_mandatory" in script
    assert "context" in script


def test_user_pages_do_not_render_tags():
    for name in ["profile.html", "my-profile.html", "app.html"]:
        page = read(name)
        assert "tag-list" not in page, name
        assert "Tag terkonfirmasi" not in page, name
    home = read("js/home.js")
    assert "matched_tags" not in home
    assert "chip" not in home
    my_profile = read("js/my-profile.js")
    assert "confirmation_status" not in my_profile
