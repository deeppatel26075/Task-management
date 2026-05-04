import json

def test_api_tasks_unauthorized(client):
    """Test that API endpoints are protected."""
    response = client.get('/api/v1/tasks')
    assert response.status_code == 401

def test_api_jwt_flow_and_crud(client, app, test_user):
    """Test full JWT token auth and REST API CRUD flow."""
    # 1. Login to get JWT
    login_resp = client.post('/api/v1/auth/login', json={
        'email': 'test@example.com',
        'password': 'password123'
    })
    assert login_resp.status_code == 200
    data = json.loads(login_resp.data)
    token = data['data']['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # 2. Add a new task via JWT
    new_task_resp = client.post('/api/v1/tasks', json={
        'title': 'Learn Flask Testing',
        'priority': 'High',
        'recurrence': 'daily',
        'category': 'Work'
    }, headers=headers)
    assert new_task_resp.status_code == 201
    task_id = json.loads(new_task_resp.data)['data']['id']

    # 3. List tasks
    list_resp = client.get('/api/v1/tasks', headers=headers)
    assert list_resp.status_code == 200
    assert len(json.loads(list_resp.data)['data']) == 1

    # 4. Update task status
    patch_resp = client.patch(f'/api/v1/tasks/{task_id}/status', json={
        'status': 'Full'
    }, headers=headers)
    assert patch_resp.status_code == 200

    # 5. Get stats summary
    stats_resp = client.get('/api/v1/stats', headers=headers)
    assert stats_resp.status_code == 200
    assert json.loads(stats_resp.data)['data']['user']['name'] == 'Test User'

    # 6. Delete task
    del_resp = client.delete(f'/api/v1/tasks/{task_id}', headers=headers)
    assert del_resp.status_code == 200
