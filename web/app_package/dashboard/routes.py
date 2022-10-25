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
from app_package.dashboard.utilsChart import make_oura_df, make_user_loc_day_df, \
    make_weather_hist_df, make_chart, buttons_dict_util, buttons_dict_update_util
from app_package.dashboard.utilsSteps import apple_hist_steps, oura_hist_util, \
    make_steps_chart_util, df_utils
import json
import os
import time



dash = Blueprint('dash', __name__)

@dash.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    print('current_User: ', current_user.email)
    page_name = 'Dashboard'

    USER_ID = current_user.id if current_user.id !=2 else 1

    any_loc_hist = sess.query(User_location_day).filter_by(user_id=USER_ID).all()
    any_oura_hist = sess.query(Oura_sleep_descriptions).filter_by(user_id=USER_ID).all()
    any_apple_data = sess.query(Apple_health_export).filter_by(user_id=USER_ID).all()

    corr_dict = False

    #make static/dashbuttons
    dash_btns_dir = os.path.join(current_app.static_folder,'dash_btns')
    sleep_dash_btns_dir = os.path.join(dash_btns_dir, 'sleep')
    
    try:
        os.makedirs(sleep_dash_btns_dir)
    except:
        print('folder exisits')

    # Buttons for dashboard table to toggle on/off correlations
    buttons_dict = {}
    user_btn_json_name = f'user{current_user.id}_buttons_dict.json'
    if request.method == 'POST':
        formDict = request.form.to_dict()

        buttons_dict = buttons_dict_util(formDict, sleep_dash_btns_dir, buttons_dict, user_btn_json_name)
        return redirect(url_for('dash.dash_steps', same_page=True))

    if os.path.exists(os.path.join(sleep_dash_btns_dir,user_btn_json_name)):
        buttons_dict = buttons_dict_update_util(sleep_dash_btns_dir, user_btn_json_name)


    # # Buttons for dashboard table to toggle on/off correlations
    # buttons_dict = {}
    # dashboard_routes_dir = os.path.join(os.getcwd(),'app_package', 'dashboard')
    # if request.method == 'POST':
    #     formDict = request.form.to_dict()

    #     buttons_dict = buttons_dict_util(formDict, dashboard_routes_dir, buttons_dict)

    # if os.path.exists(os.path.join(dashboard_routes_dir,'buttons_dict.json')):
    #     buttons_dict = buttons_dict_update_util(dashboard_routes_dir, user_btn_json_name)


    # 1) if user has apple_history
        # call def apple_hist_steps_util() -> returns df[date, sum_of_steps]

    # 2) if user has oura_history
    # call def oura_hist_steps_utils() -> returns df[date, oura_sleep_score] 

    # 3) if user has location
    # call def weather_hist() -> returns df[date, temperature, cloudiness]

    # 4) if users has all three



    if len(any_loc_hist) > 0 or len(any_oura_hist) > 0:
        
        print('*** Acceing for Strnagers Data ****')
        df_oura_scores = make_oura_df()
        if df_oura_scores is None:
            df_oura_scores = []

        df_loc_da = make_user_loc_day_df()
        if df_loc_da is None:
            df_loc_da = []

        df_weath_hist = make_weather_hist_df()
        if df_weath_hist is None:
            df_weath_hist = []


        
        # Make weather history for only days the user has locations i.e. match on date and loc_id based on df_loc_day
        df_user_date_temp = pd.merge(df_loc_da, df_weath_hist, 
            how='left', left_on=['date', 'location_id'], right_on=['date', 'location_id'])
        df_user_date_temp = df_user_date_temp[df_user_date_temp['temp'].notna()]

        print('---> THIS NEEDS TO be more than 0:::::: ', len(df_user_date_temp) )
        # print(df_user_date_temp)
        # print(df_oura_scores)

        # if user has no data return empty dashboard page
        if len(df_user_date_temp)  == 0:
            return render_template('dashboard_empty.html', page_name=page_name)


        if len(df_oura_scores) > 0 and len(df_user_date_temp) > 0:
        # if df_oura_scores is not None and df_user_date_temp is not None:
            print('-----> User has both oura and locaiton data')

            #TODO: This needs to concatenate
            df_oura_scores = df_oura_scores.set_index('date')
            df_user_date_temp = df_user_date_temp.set_index('date')

            df = pd.concat([df_user_date_temp, df_oura_scores], axis = 1)
            df.drop('id', inplace = True, axis = 1)
            df = df.where(pd.notnull(df), -99)
            df.reset_index(inplace = True)
            df['cloudcover'] = df['cloudcover'].astype(float)

            temp_data_list = [round(float(temp)) for temp in df['temp'].to_list() ]
            cloudcover_list = [round(float(cloudcover)) for cloudcover in df['cloudcover'].to_list() ]
            sleep_data_list = df['score'].to_list()
            dates_list =[datetime.strptime(i,'%Y-%m-%d') for i in df['date'].to_list() ]

            lists_tuple = (dates_list, sleep_data_list, temp_data_list, cloudcover_list)


            # resize df to remove empty avg temperature calculate correlation:
            df = df[df['temp']!=-99]   
            df = df[df.score != -99]    

            if len(df) > 2:
                print('--- Has enough observations for correlations ----')
                
                corr_dict = {}
                corr_dict['avg_temp'] = round(df['temp'].corr(df['score']),2)
                corr_dict['cloudiness'] = round(df['cloudcover'].corr(df['score']),2)
                # print(df['cloudcover'].to_list())
                # print(df.dtype)
            else:
                print('--- Has DOES NOT enough observations for correlations ----')
                corr_dict = 'too small sample'


        #If user has 
        elif len(df_oura_scores) > 0 and corr_dict==False:
            print('-----> User has only oura data')
        # elif df_oura_scores is not None:
            df_oura_scores = df_oura_scores.drop_duplicates(subset='date', keep='last')
            df = df_oura_scores.copy()
            dates_list =[datetime.strptime(i,'%Y-%m-%d') for i in df['date'].to_list() ]
            sleep_data_list = df['score'].to_list()
            temp_data_list = 'is empty'
            cloudcover_list = 'is empty'
            # lists_tuple = (dates_list, sleep_data_list, temp_data_list)
            
        elif len(df_user_date_temp) > 0 and corr_dict == False:
            print('-----> User has only locaiton data')
        # elif df_user_date_temp is not None:
            df = df_user_date_temp.copy()
            dates_list =[datetime.strptime(i,'%Y-%m-%d') for i in df['date'].to_list() ]
            temp_data_list = [round(float(temp)) for temp in df['temp'].to_list() ]
            cloudcover_list = [round(float(cloudcover)) for cloudcover in df['cloudcover'].to_list() ]
            # cloudcover_list = [cloudcover for cloudcover in df['cloudcover'].to_list() ]
            sleep_data_list = 'is empty'
            
        lists_tuple = (dates_list, sleep_data_list, temp_data_list, cloudcover_list)


        #Use list data to make chart
        script_b, div_b, cdn_js_b = make_chart(lists_tuple, buttons_dict)

        # print(script_b)

        return render_template('dashboard.html', page_name=page_name,
            script_b = script_b, div_b = div_b, cdn_js_b = cdn_js_b, corr_dict=corr_dict, buttons_dict=buttons_dict)
    else:
        df = ''

        return render_template('dashboard_empty.html', page_name=page_name)




@dash.route('/dashboard_steps', methods=['GET', 'POST'])
@login_required
def dash_steps():

    page_name = "Steps Dashboard"
    if request.referrer == request.base_url:
        same_page = True
    else:
        same_page = False

    print('request.referrer::: ', request.referrer)
    print('current url: ', request.base_url)

    USER_ID = current_user.id if current_user.id !=2 else 1

    #make static/dashbuttons
    dash_btns_dir = os.path.join(current_app.static_folder,'dash_btns')
    step_dash_btns_dir = os.path.join(dash_btns_dir, 'steps')
    
    if not os.path.exists(step_dash_btns_dir):
        os.makedirs(step_dash_btns_dir)

    # Buttons for dashboard table to toggle on/off correlations
    buttons_dict = {}
    user_btn_json_name = f'user{current_user.id}_buttons_dict.json'
    if request.method == 'POST':
        formDict = request.form.to_dict()

        buttons_dict = buttons_dict_util(formDict, step_dash_btns_dir, buttons_dict, user_btn_json_name)
        return redirect(url_for('dash.dash_steps'))

    if os.path.exists(os.path.join(step_dash_btns_dir,user_btn_json_name)):
        buttons_dict = buttons_dict_update_util(step_dash_btns_dir, user_btn_json_name)

    # Get raw df's with all the exisiting data
    df_dict = df_utils(USER_ID, step_dash_btns_dir, same_page)

    list_of_user_data = [df_name  for df_name, df in df_dict.items() if not isinstance(df, bool)]
    
    # if user has no data return empty dashboard page
    if len(list_of_user_data) == 0:
        return render_template('dashboard_empty.html', page_name=page_name)

    tuple_count = 0
    for _, df in df_dict.items():
        if not isinstance(df, bool) and tuple_count==0:
            df_all = df
            tuple_count += 1

        elif not isinstance(df, bool):
            df_all = pd.merge(df_all, df, how='outer')
            # print('---- use these column names::: ')
            # print(df_all.columns)
    
    df_all = df_all.dropna(axis=1, how='all')#remove columns with all missing values

    if len(df_all)==0:# No weather data will cause this
        return render_template('dashboard_empty.html', page_name=page_name)

    if df_all.dtypes['date'].str =='<M8[ns]':# when read from .json file df's are datetime, but should be strings
        # print('convert to string')
        df_all['date'] = df_all['date'].dt.strftime('%Y-%m-%d')

    # print('-- df_all --')
    # print(df_all.head())

    # make each column into a list series
    series_lists_dict = {}
    for col_name in df_all.columns:
        if col_name == 'date':
            series_lists_dict[col_name] =[datetime.strptime(i,'%Y-%m-%d') for i in df_all['date'].to_list() ]
        else:
            series_lists_dict[col_name] = [i for i in df_all[col_name]]
    
    # send to chart making
    script_b, div_b, cdn_js_b = make_steps_chart_util(series_lists_dict, buttons_dict)

    # 2) calcualute correlations for items that have correlations based on matching dates
    # Correlation: if more than one df and there is STEPS data then make correlation dictioanry
    corr_dict = {}
    if len(list_of_user_data)>1 and 'steps' in list_of_user_data:
        list_of_user_data.remove('steps')
        for df_name in list_of_user_data:
            df = pd.merge(df_dict['steps'], df_dict[df_name], how='outer')
            df = df[df[df_name].notna()]
            # print(' --- df_head:: ', df_name)
            # print(df.head())
            corr_dict[df_name] = round(df[df_name].corr(df['steps']),2)
            # print(f'---- Correlation for {df_name} ----')
            # print(type(corr_dict[df_name] ))
            # print(corr_dict[df_name] )
            # if corr_dict[df_name] == "nan":
            if corr_dict[df_name] != corr_dict[df_name]:# Pythonic way for checking for nan
                corr_dict[df_name] = "Not enough data"
    

    


    return render_template('dashboard_steps.html', page_name=page_name,
        script_b = script_b, div_b = div_b, cdn_js_b = cdn_js_b, corr_dict=corr_dict, buttons_dict=buttons_dict)
