from flask import Flask
from ws_config01 import ConfigDev, ConfigProd
from ws_models01 import login_manager
from flask_mail import Mail
import os
import json
import logging
from logging.handlers import RotatingFileHandler
import os

# Config Begin
config_dict = {}
if os.environ.get('TERM_PROGRAM')=='Apple_Terminal' or os.environ.get('COMPUTERNAME')=='NICKSURFACEPRO4':
    config_object = ConfigDev()
    print('* ---> Configured for Development')
    config_dict['production'] = False

else:
    config_object = ConfigProd()
    print('* ---> Configured for Production')
    config_dict['production'] = True

with open('config_dict.json', 'w') as outfile:
    json.dump(config_dict, outfile)


# Logging Begin
logs_dir = os.path.join(os.getcwd(), 'logs')

if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

logger_init = logging.getLogger('__init__')
logger_init.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(os.path.join(logs_dir,'__init__.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

logger_init.addHandler(file_handler)
logger_init.addHandler(stream_handler)

#set werkzeug handler
logging.getLogger('werkzeug').setLevel(logging.DEBUG)
logging.getLogger('werkzeug').addHandler(file_handler)
#End set up logger

logger_init.info(f'--- Starting ws08web ---')


# App init
mail = Mail()
def create_app():
    app = Flask(__name__)
    app.config.from_object(config_object)
    # print('app.config.get("ENV") says it is ---> ', app.config.get('ENV'))
    app.config.word_doc_database_images_dir = os.path.join(app.config.get('WORD_DOC_DIR'), 'blog_images')
    # app.config.word_doc_static_images_dir = os.path.join(app.config.get('WORD_DOC_DIR'), 'blog_images')

    login_manager.init_app(app)
    mail.init_app(app)

    from app_package.users.routes import users
    from app_package.dashboard.routes import dash
    from app_package.errors.routes import errors
    from app_package.blog.routes import blog
    
    app.register_blueprint(users)
    app.register_blueprint(dash)
    app.register_blueprint(errors)
    app.register_blueprint(blog)
    
    return app      
