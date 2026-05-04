import json

def test_admin_route_forbidden_for_user(client, app, test_user):
    """Test that a standard user cannot access the admin user list."""
    client.post('/login', data={
        'email': 'test@example.com',
        'password': 'password123'
    })
    resp = client.get('/admin/users')
    assert resp.status_code == 403

def test_admin_route_accessible_for_admin(client, app, admin_user):
    """Test that an admin can access the admin dashboard."""
    client.post('/login', data={
        'email': 'admin@example.com',
        'password': 'admin123'
    })
    resp = client.get('/admin/users')
    assert resp.status_code == 200
    assert b"Registered Users" in resp.data
