from bokeh.plotting import figure, output_file, show
from bokeh.embed import components
from bokeh.resources import CDN
from bokeh.io import curdoc
from bokeh.themes import built_in_themes, Theme
from bokeh.models import ColumnDataSource, Grid, LinearAxis, Plot, Text, Span
from datetime import datetime, timedelta
import os
from flask import current_app
from ws_models01 import sess, Oura_sleep_descriptions, Weather_history, User_location_day, \
    Apple_health_export
import pandas as pd
from flask_login import current_user
import json


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
    df.reset_index(inplace = True)
    
    return df


def oura_hist_util(USER_ID):

    df = create_raw_df(USER_ID, Oura_sleep_descriptions, 'oura_sleep_descriptions_')
    if isinstance(df,bool):
        return df

    df = df[['summary_date', 'score']].copy()
#     Remove duplicates keeping the last entryget latest date
    df = df.drop_duplicates(subset='summary_date', keep='last')
    df.rename(columns=({'summary_date':'date'}), inplace= True)

    return df


def user_loc_day_util(USER_ID):
    df = create_raw_df(USER_ID, User_location_day, 'user_location_day_')
    
    if isinstance(df,bool):
        return df
    # 1) get make df of user_day_location
    df = df[['date', 'location_id']]
    df= df.drop_duplicates(subset='date', keep='last')

    #2) make df of all weather [location_id, date, avg temp, cloudcover]
    df_weath_hist = create_raw_df(USER_ID, Weather_history, 'weather_history_')

    if isinstance(df_weath_hist,bool):
        return df_weath_hist

    df_weath_hist = df_weath_hist[['date_time','temp','location_id', 'cloudcover']].copy()
    df_weath_hist = df_weath_hist.rename(columns=({'date_time': 'date'}))
    
    # 3) merge on location_id and date
    df_user_date_temp = pd.merge(df, df_weath_hist, 
        how='left', left_on=['date', 'location_id'], right_on=['date', 'location_id'])
    df_user_date_temp = df_user_date_temp[df_user_date_temp['temp'].notna()]
    df_user_date_temp= df_user_date_temp[['date', 'temp', 'cloudcover']].copy()
    
    return df_user_date_temp

# def chart_util(df_dict):



