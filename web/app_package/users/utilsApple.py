from flask import current_app, url_for
from flask_login import current_user
# import json
# import requests
from datetime import datetime, timedelta
from ws_models01 import sess, engine, Apple_health_export, \
    Apple_health_steps
import time
# from flask_mail import Message
from app_package import mail
from ws_config01 import ConfigDev
import os
from werkzeug.utils import secure_filename
import zipfile
import shutil
import pandas as pd
import xmltodict

config = ConfigDev()



def make_dir_util(dir):
    try:
        os.makedirs(dir)
    except:
        print(f'{dir} already exists')


def new_apple_data_util(apple_health_dir, apple_halth_data):

    path_to_zip_file = os.path.join(apple_health_dir, secure_filename(apple_halth_data.filename))
    apple_halth_data.save(path_to_zip_file)

    #unzip
    with zipfile.ZipFile(path_to_zip_file, 'r') as zip_ref:
        zip_ref.extractall(apple_health_dir)

    #copy file to apple_health_dir and rename
    new_file_path = os.path.join(apple_health_dir,'apple_health_export','export.xml' )
    today_str = datetime.today().strftime("%Y%m%d")
    new_file_name = 'user' +str(current_user.id).zfill(4) + "_" + today_str + ".xml"
    dst_path = os.path.join(apple_health_dir,new_file_name)
    shutil.copy(new_file_path, dst_path)

    # delete .zip and apple_health_export
    os.remove(path_to_zip_file)
    shutil.rmtree(os.path.join(apple_health_dir,'apple_health_export'))

    #Add new users apple data to database
    input_path = r"C:\Users\captian2020\Documents\_jupyterNotebooks\iPhoneHealthExport\export\apple_health_export\export.xml"
    with open(dst_path, 'r') as xml_file:
        input_data = xmltodict.parse(xml_file.read())
    records_list = input_data['HealthData']['Record']
    df = pd.DataFrame(records_list)
    df['user_id'] = 1
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
