from tokenize import cookie_re
from flask import Blueprint
from flask import render_template, url_for, redirect, flash, request, abort, session,\
    Response, current_app, send_from_directory
# import bcrypt
from ws_models01 import sess, Users, login_manager, User_location_day, Oura_sleep_descriptions, \
    Apple_health_export
from flask_login import login_required, login_user, logout_user, current_user
from datetime import datetime
import numpy as np
import pandas as pd
from app_package.dashboard.utilsChart import buttons_dict_util, buttons_dict_update_util
from app_package.dashboard.utilsSteps import make_steps_chart_util, df_utils
from app_package.users.utilsDf import create_df_files
import json
import os
import time
import logging
from logging.handlers import RotatingFileHandler



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


dash = Blueprint('dash', __name__)


@dash.route('/dashboard/<dash_dependent_var>', methods=['GET', 'POST'])
@login_required
def dashboard(dash_dependent_var):
    logger_dash.info(f'- Entered dashboard: SLEEP -')
    page_name = f"{dash_dependent_var[0].upper() + dash_dependent_var[1:]} Dashboard"
    # dash_dependent_var = 'sleep'
    data_item_list = ['steps', 'sleep', 'temp', 'cloudcover']
 
    USER_ID = current_user.id if current_user.id !=2 else 1

    #make static/dashbuttons
    dash_btns_dir = os.path.join(current_app.static_folder,'dash_btns')
    sleep_dash_btns_dir = os.path.join(dash_btns_dir, 'sleep')
    
    if not os.path.exists(sleep_dash_btns_dir):
        os.makedirs(sleep_dash_btns_dir)

    # Buttons for dashboard table to toggle on/off correlations
    buttons_dict = {}
    user_btn_json_name = f'user{current_user.id}_buttons_dict.json'
    if request.method == 'POST':
        formDict = request.form.to_dict()
        print('formDict: ', formDict)
        if formDict.get('refresh_data'):
            print('let us just refersh the data')
            create_df_files(USER_ID, data_item_list)
        else:
            print('** Sleep Button pressed ** ')
            buttons_dict = buttons_dict_util(formDict, sleep_dash_btns_dir, buttons_dict, user_btn_json_name)
            print(buttons_dict)
        return redirect(url_for('dash.dashboard', dash_dependent_var=dash_dependent_var))

    # Read dict of user's chart data prefrences
    if os.path.exists(os.path.join(sleep_dash_btns_dir,user_btn_json_name)):
        buttons_dict = buttons_dict_update_util(sleep_dash_btns_dir, user_btn_json_name)
        print('** buttons_dict **')
        print(buttons_dict)

    df_dict = df_utils(USER_ID, data_item_list)

    print('**** CHECK dep_var ****')
    print(df_dict.get(dash_dependent_var))


    list_of_user_data = [df_name  for df_name, df in df_dict.items() if not isinstance(df, bool)]
    
    # if user has no data return empty dashboard page
    if len(list_of_user_data) == 0:
        message = "There is no data attached to your user. Go to accounts and add location and oura information."
        return render_template('dashboard_empty.html', page_name=page_name, message = message)
    
    # If user has no data for dash_dependent_var return empty dashboard page
    if isinstance(df_dict.get(dash_dependent_var), bool):
        message = f"You have not added any {dash_dependent_var} data to your profile. Go to your accounts page to add {dash_dependent_var} data."
        return render_template('dashboard_empty.html', page_name=page_name, message=message)

    # Create dataframe of combined data by looping over df_dict and merging df's
    tuple_count = 0
    for _, df in df_dict.items():
        if not isinstance(df, bool) and tuple_count==0:
            df_all = df
            tuple_count += 1

        elif not isinstance(df, bool):
            df_all = pd.merge(df_all, df, how='outer')
    
    df_all = df_all.dropna(axis=1, how='all')#remove columns with all missing values

    if len(df_all)==0:# No weather data will cause this
        message = "Missing weather data. Go to your accounts page and add your location to see this dashboard."
        return render_template('dashboard_empty.html', page_name=page_name, message=message)

    if df_all.dtypes['date'].str =='<M8[ns]':# when read from .json file df's are datetime, but should be strings
        # print('convert to string')
        df_all['date'] = df_all['date'].dt.strftime('%Y-%m-%d')

    # make each column into a list series
    series_lists_dict = {}
    for col_name in df_all.columns:
        if col_name == 'date':
            series_lists_dict[col_name] =[datetime.strptime(i,'%Y-%m-%d') for i in df_all['date'].to_list() ]
        else:
            series_lists_dict[col_name] = [i for i in df_all[col_name]]
    
    # print('-- series_lists_dict __')
    # print(series_lists_dict)

    # send to chart making
    script_b, div_b, cdn_js_b = make_steps_chart_util(series_lists_dict, buttons_dict)
    
    # 2) calcualute correlations for items that have correlations based on matching dates
    # Correlation: if more than one df and there is STEPS data then make correlation dictioanry
    corr_dict = {}
    
    if len(list_of_user_data)>1 and dash_dependent_var in list_of_user_data:
        list_of_user_data.remove(dash_dependent_var)
        for df_name in list_of_user_data:
            df = pd.merge(df_dict[dash_dependent_var], df_dict[df_name], how='outer')
            df = df[df[df_name].notna()]

            corr_dict[df_name] = round(df[df_name].corr(df[dash_dependent_var]),2)

            if corr_dict[df_name] != corr_dict[df_name]:# Pythonic way for checking for nan
                corr_dict[df_name] = "Not enough data"
    
    print(corr_dict)
    df_corr = pd.DataFrame.from_dict(corr_dict, orient='index')
    df_corr.rename(columns={list(df_corr)[0]:'correlation'}, inplace=True)
    df_corr['abs_corr'] = df_corr.correlation.abs()
    df_corr = df_corr.sort_values('abs_corr', ascending=False)
    corr_dict = df_corr.to_dict().get('correlation')
    corr_dict = {key: '{:,.0%}'.format(value) for key,value in corr_dict.items() }
    print(corr_dict)

    btn_names_dict = {}
    btn_names_dict['cloudcover'] = "Cloud cover"
    btn_names_dict['temp'] = "Average outdoor temperature"
    btn_names_dict['sleep'] = "Sleep score"
    btn_names_dict['steps'] = "Daily step count"


    return render_template('dashboard.html', page_name=page_name,
        script_b = script_b, div_b = div_b, cdn_js_b = cdn_js_b, corr_dict=corr_dict, 
        buttons_dict=buttons_dict, dash_dependent_var = dash_dependent_var, btn_names_dict= btn_names_dict)



# @dash.route('/dashboard_steps', methods=['GET', 'POST'])
# @login_required
# def dash_steps():
#     logger_dash.info(f'- Entered dashboard_steps -')
#     page_name = "Steps Dashboard"
#     data_item_list = ['steps', 'sleep', 'temp', 'cloudcover']
 
#     USER_ID = current_user.id if current_user.id !=2 else 1

#     #make static/dashbuttons
#     dash_btns_dir = os.path.join(current_app.static_folder,'dash_btns')
#     step_dash_btns_dir = os.path.join(dash_btns_dir, 'steps')
    
#     if not os.path.exists(step_dash_btns_dir):
#         os.makedirs(step_dash_btns_dir)

#     # Buttons for dashboard table to toggle on/off correlations
#     buttons_dict = {}
#     user_btn_json_name = f'user{current_user.id}_buttons_dict.json'
#     if request.method == 'POST':
#         formDict = request.form.to_dict()
#         print('formDict: ', formDict)
#         if formDict.get('refresh_data'):
#             print('let us just refersh the data')
#             create_df_files(USER_ID, data_item_list)
#         else:
#             buttons_dict = buttons_dict_util(formDict, step_dash_btns_dir, buttons_dict, user_btn_json_name)
#         return redirect(url_for('dash.dash_steps'))

#     if os.path.exists(os.path.join(step_dash_btns_dir,user_btn_json_name)):
#         buttons_dict = buttons_dict_update_util(step_dash_btns_dir, user_btn_json_name)
#         print('** buttons_dict **')
#         print(buttons_dict)
#     # Get raw df's with all the exisiting data
#     # df_dict = df_utils(USER_ID, step_dash_btns_dir, same_page)
    
#     df_dict = df_utils(USER_ID, data_item_list)

#     #returns dict {df_name: df}

#     list_of_user_data = [df_name  for df_name, df in df_dict.items() if not isinstance(df, bool)]

#     # print('---- Checking Dict for data in dashboard STEPS ----')

#     # print('len df_dict: ', len(df_dict))
#     # print('list_of_user_data: ', list_of_user_data)
#     # print(df_dict.get('sleep'))
    
#     # if user has no data return empty dashboard page
#     if len(list_of_user_data) == 0:
#         return render_template('dashboard_empty.html', page_name=page_name)

#     tuple_count = 0
#     for _, df in df_dict.items():
#         if not isinstance(df, bool) and tuple_count==0:
#             df_all = df
#             tuple_count += 1

#         elif not isinstance(df, bool):
#             df_all = pd.merge(df_all, df, how='outer')
#             # print('---- use these column names::: ')
#             # print(df_all.columns)
    
#     df_all = df_all.dropna(axis=1, how='all')#remove columns with all missing values

#     if len(df_all)==0:# No weather data will cause this
#         return render_template('dashboard_empty.html', page_name=page_name)

#     if df_all.dtypes['date'].str =='<M8[ns]':# when read from .json file df's are datetime, but should be strings
#         # print('convert to string')
#         df_all['date'] = df_all['date'].dt.strftime('%Y-%m-%d')


#     # make each column into a list series
#     series_lists_dict = {}
#     for col_name in df_all.columns:
#         if col_name == 'date':
#             series_lists_dict[col_name] =[datetime.strptime(i,'%Y-%m-%d') for i in df_all['date'].to_list() ]
#         else:
#             series_lists_dict[col_name] = [i for i in df_all[col_name]]
    
#     # send to chart making
#     script_b, div_b, cdn_js_b = make_steps_chart_util(series_lists_dict, buttons_dict)

#     # 2) calcualute correlations for items that have correlations based on matching dates
#     # Correlation: if more than one df and there is STEPS data then make correlation dictioanry
#     corr_dict = {}
#     if len(list_of_user_data)>1 and 'steps' in list_of_user_data:
#         list_of_user_data.remove('steps')
#         for df_name in list_of_user_data:
#             df = pd.merge(df_dict['steps'], df_dict[df_name], how='outer')
#             df = df[df[df_name].notna()]

#             corr_dict[df_name] = round(df[df_name].corr(df['steps']),2)

#             if corr_dict[df_name] != corr_dict[df_name]:# Pythonic way for checking for nan
#                 corr_dict[df_name] = "Not enough data"
    

#     return render_template('dashboard_steps.html', page_name=page_name,
#         script_b = script_b, div_b = div_b, cdn_js_b = cdn_js_b, corr_dict=corr_dict, buttons_dict=buttons_dict)
