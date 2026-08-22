import os
from app import create_app

# Instantiate the application using environment or default configuration
env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=app.config.get('DEBUG', True))
