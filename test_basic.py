"""
Basic tests for the Flask login app.

These tests mock the database layer (get_db_connection), so they run
without needing a live MySQL server. They cover routing, auth gating,
and form validation - not full DB behavior.

For tests that exercise real database reads/writes, see unit_test.py.
"""

import unittest
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash
from main import app


def mock_db_connection(fetchone_return=None):
    """Build a mock connection/cursor pair that supports the
    'with conn.cursor() as cursor:' pattern used in main.py."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_return
    mock_cursor.__enter__.return_value = mock_cursor
    mock_cursor.__exit__.return_value = False

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


class BasicRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    # --- Page loads ---

    def test_login_page_loads(self):
        response = self.app.get('/pythonlogin/')
        self.assertEqual(response.status_code, 200)

    def test_register_page_loads(self):
        response = self.app.get('/pythonlogin/register')
        self.assertEqual(response.status_code, 200)

    # --- Auth gating (no DB needed - these redirect before any query) ---

    def test_home_redirects_when_not_logged_in(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 302)

    def test_profile_redirects_when_not_logged_in(self):
        response = self.app.get('/profile')
        self.assertEqual(response.status_code, 302)

    def test_home_accessible_when_logged_in(self):
        with self.app as client:
            with client.session_transaction() as sess:
                sess['loggedin'] = True
                sess['username'] = 'testuser'
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Home Page', response.data)

    # --- Login logic (mocked DB) ---

    @patch('main.get_db_connection')
    def test_login_success(self, mock_get_conn):
        hashed = generate_password_hash('testpassword')
        fake_account = {'id': 1, 'username': 'testuser', 'password': hashed, 'email': 'testuser@example.com'}
        mock_conn, _ = mock_db_connection(fetchone_return=fake_account)
        mock_get_conn.return_value = mock_conn

        response = self.app.post('/pythonlogin/', data=dict(username='testuser', password='testpassword'))
        self.assertEqual(response.status_code, 302)

    @patch('main.get_db_connection')
    def test_login_wrong_password(self, mock_get_conn):
        hashed = generate_password_hash('correctpassword')
        fake_account = {'id': 1, 'username': 'testuser', 'password': hashed, 'email': 'testuser@example.com'}
        mock_conn, _ = mock_db_connection(fetchone_return=fake_account)
        mock_get_conn.return_value = mock_conn

        response = self.app.post('/pythonlogin/', data=dict(username='testuser', password='wrongpassword'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Incorrect username/password', response.data)

    @patch('main.get_db_connection')
    def test_login_unknown_user(self, mock_get_conn):
        mock_conn, _ = mock_db_connection(fetchone_return=None)
        mock_get_conn.return_value = mock_conn

        response = self.app.post('/pythonlogin/', data=dict(username='nobody', password='whatever'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Incorrect username/password', response.data)

    # --- Registration validation (mocked DB) ---

    @patch('main.get_db_connection')
    def test_register_invalid_email(self, mock_get_conn):
        mock_conn, _ = mock_db_connection(fetchone_return=None)  # no existing account
        mock_get_conn.return_value = mock_conn

        response = self.app.post('/pythonlogin/register', data=dict(
            username='newuser', password='pw', email='not-an-email'
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid email address', response.data)

    @patch('main.get_db_connection')
    def test_register_invalid_username(self, mock_get_conn):
        mock_conn, _ = mock_db_connection(fetchone_return=None)
        mock_get_conn.return_value = mock_conn

        response = self.app.post('/pythonlogin/register', data=dict(
            username='bad user!', password='pw', email='test@example.com'
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Username must contain only characters and numbers', response.data)

    @patch('main.get_db_connection')
    def test_register_existing_account(self, mock_get_conn):
        existing = {'id': 1, 'username': 'newuser', 'password': 'hash', 'email': 'x@example.com'}
        mock_conn, _ = mock_db_connection(fetchone_return=existing)
        mock_get_conn.return_value = mock_conn

        response = self.app.post('/pythonlogin/register', data=dict(
            username='newuser', password='pw', email='test@example.com'
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Account already exists', response.data)

    @patch('main.get_db_connection')
    def test_register_success(self, mock_get_conn):
        mock_conn, mock_cursor = mock_db_connection(fetchone_return=None)  # no existing account
        mock_get_conn.return_value = mock_conn

        response = self.app.post('/pythonlogin/register', data=dict(
            username='newuser', password='newpassword', email='newuser@example.com'
        ))
        self.assertEqual(response.status_code, 302)
        # Confirm an INSERT was attempted, and commit was called
        insert_calls = [c for c in mock_cursor.execute.call_args_list if 'INSERT' in c.args[0]]
        self.assertEqual(len(insert_calls), 1)
        mock_conn.commit.assert_called_once()

        # Password sent to the DB should be hashed, not plaintext
        inserted_password = insert_calls[0].args[1][1]
        self.assertNotEqual(inserted_password, 'newpassword')

    # --- Logout ---

    def test_logout_clears_session(self):
        with self.app as client:
            with client.session_transaction() as sess:
                sess['loggedin'] = True
                sess['username'] = 'testuser'
            response = client.get('/logout')
            self.assertEqual(response.status_code, 302)
            with client.session_transaction() as sess:
                self.assertNotIn('loggedin', sess)


if __name__ == '__main__':
    unittest.main()