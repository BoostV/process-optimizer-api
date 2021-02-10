import connexion

if __name__ == '__main__':
    app = connexion.FlaskApp(__name__, port=9090, specification_dir='./openapi/')
    app.add_api('specification.yml', arguments={'title': 'Hello World Example'})
    app.run()