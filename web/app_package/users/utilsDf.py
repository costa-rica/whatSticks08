
from datetime import datetime, timedelta
import os
# from flask import current_app
from ws_models01 import sess, Oura_sleep_descriptions, Weather_history, User_location_day, \
    Apple_health_export
import pandas as pd
# from flask_login import current_user
import json
import numpy as np
import logging
from logging.handlers import RotatingFileHandler
from ws_config01 import ConfigDev, ConfigProd

if os.environ.get('TERM_PROGRAM')=='Apple_Terminal' or os.environ.get('COMPUTERNAME')=='NICKSURFACEPRO4':
    config = ConfigDev()
    # testing = True
else:
    config = ConfigProd()
    # testing = False

logs_dir = os.path.abspath(os.path.join(os.getcwd(), 'logs'))

#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_dash = logging.getLogger(__name__)
logger_dash.setLevel(logging.DEBUG)
# logger_terminal = logging.getLogger('terminal logger')
# logger_terminal.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(logs_dir,'users_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_dash.addHandler(file_handler)
logger_dash.addHandler(stream_handler)


def create_raw_df(USER_ID, table, table_name):
    # print('*** In create_raw_df **')
    if table_name != "weather_history_":
        base_query = sess.query(table).filter_by(user_id = 1)
        df = pd.read_sql(str(base_query)[:-1] + str(USER_ID), sess.bind)
    else:
        # print('*** step 5 **')
        base_query = sess.query(table)
        df = pd.read_sql(str(base_query), sess.bind)
    if len(df) == 0:
        return False
    
    cols = list(df.columns)
    for col in cols:
        if col[:len(table_name)] == table_name:
            df = df.rename(columns=({col: col[len(table_name):]}))
    
    return df


def apple_hist_steps(USER_ID):
    df = create_raw_df(USER_ID, Apple_health_export, 'apple_health_export_')
    if isinstance(df,bool):
        return df

    df=df[df['type']=='HKQuantityTypeIdentifierStepCount']
    df['date']=df['creationDate'].str[:10]
    df=df[['date', 'value']].copy()
    df['value']=df['value'].astype(int)
    
    df = df.rename(columns=({'value': 'steps'}))
    df = df.groupby('date').sum()
    df['steps-ln'] = np.log(df.steps)
    df.reset_index(inplace = True)
    
    return df

def browse_apple_data(USER_ID):
    table_name = 'apple_health_export_'
    file_name = f'user{USER_ID}_df_browse_apple.pkl'
    file_path = os.path.join(config.DF_FILES_DIR, file_name)

    if os.path.exists(file_path):
        os.remove(file_path)

    df = create_raw_df(USER_ID, Apple_health_export, table_name)
    if not isinstance(df, bool):
        # df = create_raw_df(USER_ID, Apple_health_export, table_name)
        print('--- ')
        print(df.head())
        series_type = df[['type']].copy()
        series_type = series_type.groupby(['type'])['type'].count()

        df_type = series_type.to_frame()
        df_type.rename(columns = {list(df_type)[0]:'record_count'}, inplace=True)
        df_type.reset_index(inplace=True)

        df_type.to_pickle(file_path)
    
    #TODO: return count of all recrods
    
    # return df_type


def oura_hist_util(USER_ID):

    df = create_raw_df(USER_ID, Oura_sleep_descriptions, 'oura_sleep_descriptions_')
    if isinstance(df,bool):
        return df

    print('*******  makeing oura_hist_util ****** ')
    df = df[['summary_date', 'score']].copy()
#     Remove duplicates keeping the last entryget latest date
    df = df.drop_duplicates(subset='summary_date', keep='last')
    df.rename(columns=({'summary_date':'date', 'score':'sleep'}), inplace= True)
    df['sleep-ln'] = np.log(df.sleep)

    return df


def user_loc_day_util(USER_ID):
    df = create_raw_df(USER_ID, User_location_day, 'user_location_day_')

    if isinstance(df,bool):
        return False, False
    # 1) get make df of user_day_location
    df = df[['date', 'location_id']]
    df= df.drop_duplicates(subset='date', keep='last')

    #2) make df of all weather [location_id, date, avg temp, cloudcover]
    df_weath_hist = create_raw_df(USER_ID, Weather_history, 'weather_history_')

    if isinstance(df_weath_hist,bool):
        return False, False

    df_weath_hist = df_weath_hist[['date_time','temp','location_id', 'cloudcover']].copy()
    df_weath_hist = df_weath_hist.rename(columns=({'date_time': 'date'}))
    
    # 3) merge on location_id and date
    df_user_date_temp = pd.merge(df, df_weath_hist, 
        how='left', left_on=['date', 'location_id'], right_on=['date', 'location_id'])
    df_user_date_temp = df_user_date_temp[df_user_date_temp['temp'].notna()]
    df_user_date_temp= df_user_date_temp[['date', 'temp', 'cloudcover']].copy()
    df_user_date_temp['cloudcover'] = df_user_date_temp['cloudcover'].astype(float)
    df_user_date_temp['temp-ln']=df_user_date_temp['temp'].apply(
                                        lambda x: np.log(.01) if x==0 else np.log(x))
    df_user_date_temp['cloudcover-ln']=df_user_date_temp['cloudcover'].apply(
                                        lambda x: np.log(.01) if x==0 else np.log(x))

    df_temp = df_user_date_temp[['date', 'temp', 'temp-ln']].copy()
    df_cloud = df_user_date_temp[['date', 'cloudcover', 'cloudcover-ln']].copy()

    return df_temp, df_cloud



# def df_utils(USER_ID, step_dash_btns_dir, same_page):
def create_df_files(USER_ID, data_item_list):

    # Items names in data_item_list must match column name

    # create file dictionary {data_item_name: path_to_df (but no df yet)}
    file_dict = {}
    for data_item in data_item_list:
        # temp_file_name = f'user{USER_ID}_df_{data_item}.json'
        temp_file_name = f'user{USER_ID}_df_{data_item}.pkl'
        file_dict[data_item] = os.path.join(config.DF_FILES_DIR, temp_file_name)

    # Remove any existing df for user
    for _, f in file_dict.items():
        if os.path.exists(f):
            os.remove(f)


    df_dict = {}
    
    # Make DF for each in database/df_files/
    for data_item, file_path in file_dict.items():
        if not os.path.exists(file_path):
            if data_item == 'steps':
                df_dict[data_item] = apple_hist_steps(USER_ID)
                # if not isinstance(df_dict['steps'], bool): df_dict['steps'].to_json(file_path)
                if not isinstance(df_dict['steps'], bool): df_dict['steps'].to_pickle(file_path)
                #create brows_data_df
                browse_apple_data(USER_ID)
            elif data_item == 'sleep':
                df_dict[data_item] = oura_hist_util(USER_ID)
                # if not isinstance(df_dict['sleep'], bool): df_dict['sleep'].to_json(file_path)
                if not isinstance(df_dict['sleep'], bool): df_dict['sleep'].to_pickle(file_path)
            if data_item =='temp':
                df_dict['temp'], _ = user_loc_day_util(USER_ID)
                # if not isinstance(df_dict['temp'] , bool): df_dict['temp'] .to_json(file_path)
                if not isinstance(df_dict['temp'] , bool): df_dict['temp'] .to_pickle(file_path)
            elif data_item == 'cloudcover':
                _, df_dict['cloudcover'] = user_loc_day_util(USER_ID)
                # if not isinstance(df_dict['cloudcover'] , bool): df_dict['cloudcover'] .to_json(file_path)
                if not isinstance(df_dict['cloudcover'] , bool): df_dict['cloudcover'] .to_pickle(file_path)
        else:
            # df_dict[data_item] = pd.read_json(file_path)
            df_dict[data_item] = pd.read_pickle(file_path)
            logger_dash.info(f'--- Does this DF every get made ???? ---')


    return df_dict