"""
Main server
"""
import os
import connexion
from waitress import serve
from .securepickle import get_crypto

if __name__ == '__main__':
    # Initialize crypto
    get_crypto()
    app = connexion.FlaskApp(
        __name__, port=9090, specification_dir='./openapi/')
    app.add_api('specification.yml', arguments={
                'title': 'Hello World Example'})
    if os.getenv("FLASK_ENV", "development") == "development":
        os.environ["FLASK_ENV"] = "development"
        app.run()
    else:
        serve(app, listen='*:9090')
