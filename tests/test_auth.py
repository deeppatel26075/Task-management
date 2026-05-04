import json

def test_user_registration(client, app):
    """Test user registration flow."""
    resp = client.post('/register', data={
        'name': 'Bob Ross',
        'email': 'bob@example.com',
        'password': 'happytrees123'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Analytics" in resp.data or b"Dashboard" in resp.data

def test_user_login_and_logout(client, app, test_user):
    """Test login and logout using standard session cookie."""
    login_resp = client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    assert login_resp.status_code == 200
    assert b"Dashboard" in login_resp.data

    logout_resp = client.get('/logout', follow_redirects=True)
    assert logout_resp.status_code == 200
    assert b"Login" in logout_resp.data or b"Register" in logout_resp.data
