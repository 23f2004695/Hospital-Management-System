import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Debug mode exposes an interactive console, so it's off unless you ask for it,
    # and the server only listens on this machine by default
    app.run(
        debug=os.environ.get('FLASK_DEBUG') == '1',
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', 5001)),
    )
