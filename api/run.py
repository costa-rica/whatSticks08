from app_package import create_app

app = create_app()

if __name__ == '__main__':
    app.run(port=5001)
    # app.run()