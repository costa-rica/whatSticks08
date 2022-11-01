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
import numpy as np
import logging
from logging.handlers import RotatingFileHandler
from ws_config01 import ConfigDev, ConfigProd


if os.environ.get('TERM_PROGRAM')=='Apple_Terminal' or os.environ.get('COMPUTERNAME')=='NICKSURFACEPRO4':
    config = ConfigDev()
else:
    config = ConfigProd()


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
file_handler = RotatingFileHandler(os.path.join(logs_dir,'dashboard_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
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


def get_df_for_dash(USER_ID, data_item):
    file_name = f'user{USER_ID}_df_{data_item}.pkl'
    file_path = os.path.join(config.DF_FILES_DIR, file_name)
    print('-- file_path --')
    print(file_path)
    if not os.path.exists(file_path):
        return False

    df = pd.read_pickle(file_path)
    print(f'** DF for : {data_item}')
    print(df.head())
    return df


# def user_loc_day_util(USER_ID):
#     df = create_raw_df(USER_ID, User_location_day, 'user_location_day_')

#     if isinstance(df,bool):
#         return False, False
#     # 1) get make df of user_day_location
#     df = df[['date', 'location_id']]
#     df= df.drop_duplicates(subset='date', keep='last')

#     #2) make df of all weather [location_id, date, avg temp, cloudcover]
#     df_weath_hist = create_raw_df(USER_ID, Weather_history, 'weather_history_')

#     if isinstance(df_weath_hist,bool):
#         return False, False

#     df_weath_hist = df_weath_hist[['date_time','temp','location_id', 'cloudcover']].copy()
#     df_weath_hist = df_weath_hist.rename(columns=({'date_time': 'date'}))
    
#     # 3) merge on location_id and date
#     df_user_date_temp = pd.merge(df, df_weath_hist, 
#         how='left', left_on=['date', 'location_id'], right_on=['date', 'location_id'])
#     df_user_date_temp = df_user_date_temp[df_user_date_temp['temp'].notna()]
#     df_user_date_temp= df_user_date_temp[['date', 'temp', 'cloudcover']].copy()
#     df_user_date_temp['cloudcover'] = df_user_date_temp['cloudcover'].astype(float)
#     df_user_date_temp['temp-ln']=df_user_date_temp['temp'].apply(
#                                         lambda x: np.log(.01) if x==0 else np.log(x))
#     df_user_date_temp['cloudcover-ln']=df_user_date_temp['cloudcover'].apply(
#                                         lambda x: np.log(.01) if x==0 else np.log(x))

#     df_temp = df_user_date_temp[['date', 'temp', 'temp-ln']].copy()
#     df_cloud = df_user_date_temp[['date', 'cloudcover', 'cloudcover-ln']].copy()

#     return df_temp, df_cloud


def make_steps_chart_util(series_lists_dict, buttons_dict):
    print('-- utilsSteps make_steps_chart_util --')

    print(series_lists_dict.keys())

    print('- buttons_dict -')
    plot_font_size = "1rem"
    dates_list = series_lists_dict.get('date')
    date_start = max(dates_list) - timedelta(days=8.5)
    date_end = max(dates_list) + timedelta(days=1)
    print('waht is hte last date:', dates_list[-1])
    fig1=figure(toolbar_location=None,tools='xwheel_zoom,xpan',active_scroll='xwheel_zoom',

            x_range=(date_start,date_end),
            y_range=(-5,12),sizing_mode='stretch_width', height=400)

#Temperature
    if series_lists_dict.get('temp'):
        print('--- Is ther temp in the series_list_dict ???? ')
        temp_list = series_lists_dict.get('temp')
        temp_ln_list = series_lists_dict.get('temp-ln')
        if buttons_dict.get('temp') !=1:
            fig1.circle(dates_list,temp_ln_list, 
                legend_label="Temperature (F)", 
                fill_color='#c77711', 
                line_color=None,
                size=30)

            source1 = ColumnDataSource(dict(x=dates_list, y=temp_ln_list, text=temp_list)) # data
            glyph1 = Text(text="text",text_font_size={'value': plot_font_size},x_offset=-10, y_offset=10) # Image
            fig1.add_glyph(source1, glyph1)

#cloud cover
    if series_lists_dict.get('cloudcover'):
        # print('--- Is ther cloudcover in the series_list_dict ???? ')
        cloud_list = series_lists_dict.get('cloudcover')
        cloud_ln_list = series_lists_dict.get('cloudcover-ln')
        if buttons_dict.get('cloudcover') !=1:
            fig1.circle(dates_list,cloud_ln_list, 
                legend_label="Cloudcover", 
                fill_color='#6cacc3', 
                line_color="#3288bd",
                size=30, line_width=3)

            source1_cloud = ColumnDataSource(dict(x=dates_list, y=cloud_ln_list, text=cloud_list)) # data
            glyph1_cloud = Text(text="text",text_font_size={'value': plot_font_size},x_offset=-10, y_offset=10) # Image
            fig1.add_glyph(source1_cloud, glyph1_cloud)

#sleep rectangle label
    if series_lists_dict.get('sleep'):
        sleep_list = series_lists_dict.get('sleep')
        sleep_ln_list = series_lists_dict.get('sleep-ln')
        if buttons_dict.get('sleep') !=1:
            fig1.square(dates_list, sleep_ln_list, legend_label = 'Oura Sleep Score', size=30, color="olive", alpha=0.5)
            
            source4 = ColumnDataSource(dict(x=dates_list, y=sleep_ln_list,
                text=sleep_list))
            glyph4 = Text(text="text",text_font_size={'value': plot_font_size},x_offset=-10, y_offset=10)
            fig1.add_glyph(source4, glyph4)

#steps rectangle label
    if series_lists_dict.get('steps'):
        steps_list = series_lists_dict.get('steps')
        steps_ln_list = series_lists_dict.get('steps-ln')
        if buttons_dict.get('steps') !=1:
            fig1.square(dates_list, steps_ln_list, legend_label = 'Daily Steps', size=30, color="gray", alpha=0.5)
            
            source4 = ColumnDataSource(dict(x=dates_list, y=steps_ln_list,
                text=steps_list))
            glyph4 = Text(text="text",text_font_size={'value': plot_font_size},x_offset=-10, y_offset=10)
            fig1.add_glyph(source4, glyph4)


    fig1.ygrid.grid_line_color = None
    fig1.yaxis.major_label_text_color = None
    fig1.yaxis.major_tick_line_color = None
    fig1.yaxis.minor_tick_line_color = None

    fig1.legend.background_fill_color = "#578582"
    fig1.legend.background_fill_alpha = 0.2
    fig1.legend.border_line_color = None
    fig1.legend.label_text_font_size ='1.3rem'
    fig1.xaxis.major_label_text_font_size = '1.3rem'
    # fig1.xaxis.axis_label = 'whatever'
    theme_1=curdoc().theme = Theme(filename=os.path.join(current_app.static_folder, 'chart_theme_2.yml'))

    script1, div1 = components(fig1, theme=theme_1)

    cdn_js=CDN.js_files

    return script1, div1, cdn_js



def df_utils(USER_ID, data_item_list):
    # Make DF for each 
    # file_dict = { data_item: f'user{USER_ID}_df_{data_item}.json' for data_item in data_item_list}
    file_dict ={}
    for data_item in data_item_list:
        # file_name = f'user{USER_ID}_df_{data_item}.json'
        file_name = f'user{USER_ID}_df_{data_item}.pkl'
        file_path = os.path.join(config.DF_FILES_DIR, file_name)
        file_dict[data_item] = file_path
    
    df_dict = {}

    for data_item, file_path in file_dict.items():

        # if data_item =='temp':
        #     df_dict['temp'], _ = user_loc_day_util(USER_ID)
        #     if not isinstance(df_dict['temp'] , bool): df_dict['temp'] .to_pickle(file_path)
        # elif data_item == 'cloudcover':
        #     _, df_dict['cloudcover'] = user_loc_day_util(USER_ID)
        #     if not isinstance(df_dict['cloudcover'] , bool): df_dict['cloudcover'] .to_pickle(file_path)
        # else:# Steps and oura can go here
        df_dict[data_item] = get_df_for_dash(USER_ID, data_item)

    return df_dict
