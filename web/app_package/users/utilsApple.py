from flask import current_app, url_for
from flask_login import current_user
from datetime import datetime, timedelta
from ws_models01 import sess, engine, Apple_health_export
import time
from app_package import mail
from ws_config01 import ConfigDev, ConfigProd
import os
from werkzeug.utils import secure_filename
import zipfile
import shutil
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler

if os.environ.get('TERM_PROGRAM')=='Apple_Terminal' or os.environ.get('COMPUTERNAME')=='NICKSURFACEPRO4':
    config = ConfigDev()
    testing = True
else:
    config = ConfigProd()
    testing = False

logs_dir = os.path.abspath(os.path.join(os.getcwd(), 'logs'))

#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_users = logging.getLogger(__name__)
logger_users.setLevel(logging.DEBUG)
# logger_terminal = logging.getLogger('terminal logger')
# logger_terminal.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(logs_dir,'users_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_users.addHandler(file_handler)
logger_users.addHandler(stream_handler)


def report_process_time(start_post_time):
        
    end_post_time = time.time()
    run_seconds = round(end_post_time - start_post_time)
    if run_seconds <60:
        return f"---run_time: {str(run_seconds)} seconds"
    elif run_seconds > 60:
        run_minutes =  round(run_seconds / 60)
        return f"--- run_time: {str(run_minutes)} mins and {str(run_seconds % 60)} seconds"

def make_dir_util(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)
        logger_users.info(f'- Created {dir}')


def decompress_and_save_apple_health(apple_health_dir, apple_health_data):

    path_to_zip_file = os.path.join(apple_health_dir, secure_filename(apple_health_data.filename))
    apple_health_data.save(path_to_zip_file)

    #unzip
    with zipfile.ZipFile(path_to_zip_file, 'r') as zip_ref:
        zip_ref.extractall(apple_health_dir)

    #copy file to apple_health_dir and rename
    new_file_path = os.path.join(apple_health_dir,'apple_health_export','export.xml' )
    today_str = datetime.today().strftime("%Y%m%d")
    new_file_name = 'user' +str(current_user.id).zfill(4) + "_" + today_str + ".xml"
    new_file_path_dest = os.path.join(apple_health_dir,new_file_name)
    logger_users.info(f"--- new_apple_data_util ---")
    logger_users.info('new_file_path')
    logger_users.info(new_file_path)

    shutil.copy(new_file_path, new_file_path_dest)

    # delete .zip and apple_health_export
    os.remove(path_to_zip_file)
    shutil.rmtree(os.path.join(apple_health_dir,'apple_health_export'))

    return new_file_path_dest



def add_apple_to_db(xml_dict):
    #Add new users apple data to database

    ##########
    # XML already converted to dictionary #
    ###############################

    records_list = xml_dict['HealthData']['Record']
    df = pd.DataFrame(records_list)
    df['user_id'] = current_user.id
    df['time_stamp_utc']=datetime.utcnow()
    for name in list(df.columns):
        if name.find('@')!=-1:
            df.rename(columns={name:name[1:]}, inplace=True)

# Columns with dictionary structures i di'tn kwon what to do with
    df.MetadataEntry=''
    df.HeartRateVariabilityMetadataList=''

    #get all user's existing apple_health data into df
    base_query = sess.query(Apple_health_export).filter_by(user_id = 1)
    df_existing = pd.read_sql(str(base_query)[:-1] + str(current_user.id), sess.bind)

    print(f'current user has {len(df_existing)} rows')
    #rename columns

    table_name = 'apple_health_export_'
    cols = list(df_existing.columns)
    for col in cols:
        if col[:len(table_name)] == table_name:
            df_existing = df_existing.rename(columns=({col: col[len(table_name):]}))

    df_existing.set_index(['user_id','type', 'sourceName','creationDate'], inplace=True)
    df.set_index(['user_id','type', 'sourceName','creationDate'], inplace=True)
    df = df[~df.index.isin(df_existing.index)]
    df.reset_index(inplace=True)
    print('Removed Exiisting rows from new dataset')
    print(len(df))

    print('Adding new data')
    #add to database
    df.to_sql('apple_health_export', con=engine, if_exists='append', index=False)

    return len(df)
