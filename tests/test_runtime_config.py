"""Small self-check for the imported backend's runtime security defaults."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['SFM_DATABASE_PATH'] = str(Path(temp_dir) / 'test.db')
        os.environ['SFM_LOG_DIR'] = str(Path(temp_dir) / 'logs')
        os.environ['SFM_API_TOKEN'] = 'test-token'

        from src.app import app

        client = app.test_client()
        assert client.get('/api/inventory').status_code == 401
        response = client.get(
            '/api/inventory',
            headers={'Authorization': 'Bearer test-token'}
        )
        assert response.status_code == 200


if __name__ == '__main__':
    main()
    print('runtime config self-check passed')
