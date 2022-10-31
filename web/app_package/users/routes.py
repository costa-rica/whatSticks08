from contextlib import redirect_stderr
from flask import Blueprint
from flask import render_template, url_for, redirect, flash, request, \
    abort, session, Response, current_app, send_from_directory, make_response
import bcrypt
from ws_models01 import sess, Users, login_manager, Oura_token, Locations, \
    Weather_history, User_location_day, Oura_sleep_descriptions, Posts, Apple_health_export
from flask_login import login_required, login_user, logout_user, current_user
import requests
#Oura
from app_package.users.utils import oura_sleep_call, oura_sleep_db_add
#Location
from app_package.users.utils import call_location_api, location_exists, \
    add_weather_history, gen_weather_url, add_new_location
#Email
from app_package.users.utils import send_reset_email
#Apple
from app_package.users.utilsApple import make_dir_util, decompress_and_save_apple_health, \
    add_apple_to_db, report_process_time
from app_package.users.utilsXmlUtility import xml_file_fixer, compress_to_save_util

from app_package.dashboard.utilsSteps import create_raw_df

from sqlalchemy import func
from datetime import datetime, timedelta
import time
import logging
from logging.handlers import RotatingFileHandler
import os
import json
from ws_config01 import ConfigDev, ConfigProd
import xmltodict

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


salt = bcrypt.gensalt()


users = Blueprint('users', __name__)

@users.route('/', methods=['GET', 'POST'])
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dash.dashboard'))


    latest_post = sess.query(Posts).all()
    if len(latest_post) > 0:
        latest_post = latest_post[-1]

        blog = {}
        keys = latest_post.__table__.columns.keys()
        blog = {key: getattr(latest_post, key) for key in keys}
        blog['blog_name']='blog'+str(latest_post.id).zfill(4)
        blog['date_published'] = blog['date_published'].strftime("%b %d %Y")
        print(blog)
    else:
        blog =''


    if request.method == 'POST':
        formDict = request.form.to_dict()
        if formDict.get('login'):
            return redirect(url_for('users.login'))
        elif formDict.get('register'):
            return redirect(url_for('users.register'))

    return render_template('home.html', blog=blog)

@users.route('/login', methods = ['GET', 'POST'])
def login():
    print('* in login *')
    if current_user.is_authenticated:
        return redirect(url_for('dash.dash_steps'))
    page_name = 'Login'
    if request.method == 'POST':
        formDict = request.form.to_dict()
        print('**** formDict ****')
        print(formDict)
        email = formDict.get('email')

        user = sess.query(Users).filter_by(email=email).first()
        print('user for logging in:::', user)
        # verify password using hash
        password = formDict.get('password_text')

        if user:
            if password:
                if bcrypt.checkpw(password.encode(), user.password):
                    print("match")
                    login_user(user)
                    # flash('Logged in succesfully', 'info')

                    return redirect(url_for('dash.dash_steps'))
                else:
                    flash('Password or email incorrectly entered', 'warning')
            else:
                flash('Must enter password', 'warning')
        elif formDict.get('btn_login_as_guest'):
            print('GUEST EMAIL::: ', current_app.config['GUEST_EMAIL'])
            user = sess.query(Users).filter_by(id=2).first()
            login_user(user)
            # flash('Logged in succesfully as Guest', 'info')

            return redirect(url_for('dash.dash_steps'))
        else:
            flash('No user by that name', 'warning')

        # if successsful login_something_or_other...



    return render_template('login.html', page_name = page_name)

@users.route('/register', methods = ['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dash.dashboard'))
    page_name = 'Register'
    if request.method == 'POST':
        formDict = request.form.to_dict()
        new_email = formDict.get('email')

        check_email = sess.query(Users).filter_by(email = new_email).all()
        if len(check_email)==1:
            flash(f'The email you entered already exists you can sign in or try another email.', 'warning')
            return redirect(url_for('users.register'))

        hash_pw = bcrypt.hashpw(formDict.get('password_text').encode(), salt)
        new_user = Users(email = new_email, password = hash_pw)
        sess.add(new_user)
        sess.commit()
        flash(f'Succesfully registerd: {new_email}', 'info')
        return redirect(url_for('users.login'))

    return render_template('register.html', page_name = page_name)


@users.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('users.home'))


@users.route('/account', methods = ['GET', 'POST'])
@login_required
def account():
    logger_users.info(f"--- user accessed Accounts")
    page_name = 'Account Page'
    email = current_user.email

    logger_users.info(f'Current User: {current_user.email}')

    user = sess.query(Users).filter_by(id = current_user.id).first()

    if user.lat == None or user.lat == '':
        existing_coordinates = ''
        city_name = ''
    else:
        existing_coordinates = f'{user.lat}, {user.lon}'
        location =sess.query(Locations).get(location_exists(user))
        city_name = f"{location.city}, {location.country}"


    if request.method == 'POST':
        if current_user.id == 2:
            flash('Guest can enter any values but they will not change the database', 'info')
            return redirect(url_for('users.account'))
        else:
            startTime_post = time.time()
            formDict = request.form.to_dict()
            # new_token = formDict.get('oura_token')
            new_location = formDict.get('location_text')
            email = formDict.get('email')
            # user = sess.query(Users).filter_by(id = current_user.id).first()
            yesterday = datetime.today() - timedelta(days=1)
            yesterday_formatted =  yesterday.strftime('%Y-%m-%d')
            # user_loc_days = sess.query(User_location_day).filter_by(user_id=current_user.id).all()
            # user_loc_days_date_dict = {i.date : i.id for i in user_loc_days}
            # print(formDict)



            # #1) User adds Oura_token data
            # if new_token != existing_oura_token_str:#<-- if new token is different
            #     print('------ New token detected ------')
            #     #1-1a) if user has token replace it
            #     if existing_oura_token:
            #         existing_oura_token.token = new_token
            #         sess.commit()
            #         oura_token_id = existing_oura_token.id
            #         print('Existing token')
            #     #1-1b) else add new token
            #     else:
            #         print('Completely new token')
            #         new_oura_token = Oura_token(user_id = current_user.id,
            #             token = new_token)
            #         sess.add(new_oura_token)
            #         sess.commit()

            #         oura_token_id = new_oura_token.id

            #     #1-1b-1) check if user has oura data yesterday
            #     oura_yesterday = sess.query(Oura_sleep_descriptions).filter_by(
            #         user_id = current_user.id,
            #         summary_date = yesterday_formatted).first()

            #     # --> 1-1b-1b) if no data yesterday, call API
            #     if not oura_yesterday and new_token != '':
            #         sleep_dict = oura_sleep_call(new_token)

            #         if isinstance(sleep_dict,dict):
            #             sessions_added = oura_sleep_db_add(sleep_dict, oura_token_id)
            #             flash(f'Successfully added {str(sessions_added)} sleep sesions and updated user Oura Token', 'info')
            #         else:
            #             print(f'** Unable to get data from Oura API becuase {sleep_dict}')
            #             flash(f'Unable to get data from Oura API becuase {sleep_dict}', 'warning')
            #     elif not new_token:
            #         flash('User oura token successfully removed','info')
            #         print('** removed oura token from user')
            #     else:
            #         print('-- date detected yesterday for this user')
            #         print(oura_yesterday)


            #2) User adds location data
            if new_location != existing_coordinates:
                if new_location == '':                          #<--- User is removing their location data
                    user.lat = None
                    user.lon = None
                    sess.commit()
                    flash('User coordinates removed succesfully','info')

                else:                                           #<-- User is updating their location
                    # add lat/lon to users table
                    user.lat = formDict.get('location_text').split(',')[0]
                    user.lon = formDict.get('location_text').split(',')[1]
                    sess.commit()
                    logger_users.info('---- Added new coordinates for user ----')

                    location_id = location_exists(user)# --------- Check if coordinates are in Locations table
                    if location_id == 0:     #<--- Coordinates NOT in database
                        logger_users.info('--- location does not exist, in process of adding ---')
                        location_api_response = call_location_api(user)
                        if isinstance(location_api_response,dict):
                            location_id = add_new_location(location_api_response)

                    else:   #<--- Coordinates in database
                        logger_users.info('--- location already exists in WS database ----')

                    # make list of past 14 days [Y-M-D]
                    today = datetime.now()
                    today_list = [(today-timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1,15)]

                    # Add/update user_loc_day for all in list

                    for day in today_list:
                        user_loc_day_hist = sess.query(User_location_day).filter_by(user_id=current_user.id, date=day).first()
                        if user_loc_day_hist:
                            sess.query(User_location_day).filter_by(user_id = current_user.id , date=day).delete()
                            sess.commit()

                        new_user_loc_day = User_location_day(user_id=current_user.id,
                            location_id = location_id,
                            date = day,
                            # local_time = f"{str(datetime.now().hour)}:{str(datetime.now().minute)}",
                            row_type='user input')
                        sess.add(new_user_loc_day)
                        sess.commit()


                    # flash(f"Updated user's location and add weather history", 'info')
                    weather_api_trouble = False
                    for day in today_list:
                        loc_day_weather_hist = sess.query(Weather_history).filter_by(location_id=location_id, date_time=day).first()
                        if loc_day_weather_hist is None:
                            logger_users.info(f'--- Calling Weather api for {day} in loc_id: {location_id} ----')
                            weather_api_response = requests.get(gen_weather_url(location_id, day))
                            if weather_api_response.status_code == 200:
                                add_weather_history(weather_api_response, location_id)
                            else:
                                logger_users.info(f'--- Bad API call for Weather history {day} in location_id: {location_id} ----')
                                logger_users.info(f'--- Status code: {weather_api_response.status_code} ----')
                                weather_api_trouble = True


                        else:
                            logger_users.info(f'--- Weather history already exists for {day} in loc_id: {location_id} ----')

                    if weather_api_trouble == True:
                        flash("Some days might not have been updated with weather due to problems with Weather API", "info")
                    else:
                        flash("Recent weather history updated!", "success")

                #     if weather_api_response.status_code == 200:
                # #2-1b-2) use response to populate yesterday's history in WEather_history
                #         logger_users.info('** Adding weather history')
                #         add_weather_history(weather_api_response, location_id)
                #         flash('Succesfully added user location', 'info')
                #     else:
                #         logger_users.info('** FAILING to adding weather history')
                #         flash(f"Unable to add weather history - problem communicating with Visual Crossing", 'warning')

                # #Add User_Loc_day
                #     yesterday = datetime.today() - timedelta(days=1)
                #     yesterday_formatted =  yesterday.strftime('%Y-%m-%d')
                #     new_user_loc_day = User_location_day(
                #         user_id = user.id,
                #         location_id = location_id,
                #         local_time = f"{str(datetime.now().hour)}:{str(datetime.now().minute)}",
                #         date = yesterday_formatted,
                #         row_type = 'user input'
                #     )
                #     sess.add(new_user_loc_day)
                #     sess.commit()

                #new #2-1b-2) call weather history
                    # call_weather_api(location_id, today)
                    # weather_api_response = requests.get(gen_weather_url(location_id, yesterday_formatted))
                    # logger_users.info(f'weather_api_response status code: {weather_api_response.status_code}')





            #3) User changes email
            if email != user.email:

                #check that not blank
                if email == '':
                    flash('Must enter a valid email.', 'warning')
                    return redirect(url_for('users.account'))

                #check that email doesn't alreay exist outside of current user
                other_users_email_list = [i.email for i in sess.query(Users).filter(Users.id != current_user.id).all()]

                if email in other_users_email_list:
                    flash('That email is being used by another user. Please choose another.', 'warning')
                    return redirect(url_for('users.account'))

                #update user email
                user.email = email
                sess.commit()
                flash('Email successfully updated.', 'info')
                return redirect(url_for('users.account'))

            #END of POST
            executionTime = (time.time() - startTime_post)
            logger_users.info('POST time in seconds: ' + str(executionTime))
            return redirect(url_for('users.account'))


    return render_template('accounts.html', page_name = page_name, email=email,
        location_coords = existing_coordinates, city_name = city_name)



@users.route('/add_apple', methods=["GET", "POST"])
def add_apple():


    existing_records = sess.query(Apple_health_export).filter_by(user_id=current_user.id).all()
    apple_records = "{:,}".format(len(existing_records))

    # make APPLE_HEALTH_DIR
    apple_health_dir = current_app.config.get('APPLE_HEALTH_DIR')
    make_dir_util(apple_health_dir)

    logger_users.info(f"--- POSTING Apple Health Data (user: {current_user.id}) ---")
    start_post_time = time.time()

    if request.method == 'POST':
        if current_user.id ==2:
            flash("Guest cannot change data. Register and then add data.", "info")
            return redirect(url_for('users.add_apple'))
        filesDict = request.files
        apple_health_data = filesDict.get('apple_health_data')

        # logger_users.info('---- filesDict ----')
        # logger_users.info(filesDict)
        # logger_users.info('---- file name ----')
        if filesDict.get('apple_health_data'):
            logger_users.info(filesDict.get('apple_health_data').filename)


        formDict = request.form.to_dict()
        # logger_users.info('- formDict -')
        # logger_users.info(formDict)


        #4) Apple health data
        if apple_health_data:


            # Measuring file loading time and size
            filesize = float(request.cookies.get('filesize'))
            filesize_mb = round(filesize/ 10**6,1)
            filesize = "{:,}".format(filesize_mb)
            logger_users.info(f"Compressed filesize: {filesize} Mb")


            new_file_path = decompress_and_save_apple_health(apple_health_dir, apple_health_data)
            xml_file_name = os.path.basename(new_file_path)
            # new_rec_count = 9

            filesize_mb = os.stat(new_file_path).st_size / (1024 * 1024)
            logger_users.info(f"--- Decompressed Apple Health Export file size: {filesize_mb} MB ---")

            # 1) if size small try to xmltodict

            if filesize_mb < 100:
                logger_users.info(f"--- Apple export is small processing file while user waits ---")
                try:

                    with open(new_file_path, 'r') as xml_file:
                        xml_dict = xmltodict.parse(xml_file.read())
                    
                except:
                    #Trying to fix file
                    logger_users.info(f'---- xmltodict failed first go around. Sending to xml_file_fixer --')
                    xml_dict = xml_file_fixer(new_file_path)
                    if isinstance(xml_dict, str):
                        logger_users.info(f'---- Failed to process Apple file. No header for data found')
                        flash('Failed to process Apple file. No header for data found', 'warning')
                        return redirect(url_for('users.add_apple'))
                
                try:
                    df_uploaded_record_count = add_apple_to_db(xml_dict)
                    logger_users.info('- Successfully added xml to database!')

                except:
                    logger_users.info('---- Failed to add data to database')
                    return redirect(url_for('users.add_apple'))
                # Store successful download in compressed version of /databases/apple_health_data/...
                print(new_file_path)
                compress_to_save_util(os.path.basename(new_file_path))
            else:
                logger_users.info(f"--- Apple export is large. Send to API. Email user when complete ---")
                headers = { 'Content-Type': 'application/json'}
                payload = {}
                payload['password'] = config.WSH_API_PASSWORD
                payload['user_id'] = current_user.id
                payload['xml_file_name'] = xml_file_name
                r_store_apple = requests.request('GET', config.WSH_API_URL_BASE + '/store_apple_health', headers=headers, 
                                 data=str(json.dumps(payload)))
                logger_users.info(f'-- Sent api file processing request. Response status code: {r_store_apple.status_code}')
                
        ##### TODO: intentional ERROR so the javascript flag is warning that the user will be emailed ***
                return redirect(url_for('user.add_apple'))
                
            logger_users.info(report_process_time(start_post_time))

            if isinstance(df_uploaded_record_count, str):
                flash('This file cannot be read. Contact nick@dashanddata.com if you would like him to fix it', 'warning')
                return redirect(url_for('users.add_apple'))


            # At this point we already know if the file can be used or not
            flash(f"succesfully saved {'{:,}'.format(df_uploaded_record_count)} records from apple export", 'info')

        elif formDict.get('btn_delete_apple_data'):
            logger_users.info('- delete apple data -')


            # print('Delete apple data')
            rows_deleted = sess.query(Apple_health_export).filter_by(user_id = current_user.id).delete()
            sess.commit()
            flash(f"Removed {'{:,}'.format(rows_deleted)} Apple Health records from What Sticks data storage", 'warning')


        return redirect(url_for('users.add_apple'))
    return render_template('add_apple.html', apple_records=apple_records)


users.route('/redirect_test', methods=['GET', 'POST'])
def redirect_test():
    return redirect(url_for('users.add_apple', test_var='Stop sending'))


@users.route('/add_more_apple', methods=['GET', 'POST'])
def add_more_apple():
    table_name = 'apple_health_export_'
    USER_ID = current_user.id if current_user.id !=2 else 1
    df = create_raw_df(USER_ID, Apple_health_export, table_name)
    print('--- ')
    # print(df.head())
    df_type = df[['type']].copy()
    df_type = df_type.groupby(['type'])['type'].count()
    # df_type.rename(columns = {list(df_type)[1]: 'record_count'}, inplace = True)
    # df_type.style.format({"record_count": "{:,.0f}"})
    print(df_type.head())
    df_dict = df_type.to_dict()
    # print(df_dict.keys())
    # print('------')
    # print(df_dict)

    return render_template('add_apple_more.html', df_dict=df_dict)


@users.route('/add_oura', methods=["GET", "POST"])
def add_oura():
    logger_users.info(f"--- Add Oura route ---")
    existing_records = sess.query(Oura_sleep_descriptions).filter_by(user_id=current_user.id).all()
    oura_sleep_records = "{:,}".format(len(existing_records))

    existing_oura_token =sess.query(Oura_token, func.max(
        Oura_token.id)).filter_by(user_id=current_user.id).first()[0]


    if existing_oura_token:
        oura_token = current_user.oura_token_id[-1].token
        existing_oura_token_str = str(existing_oura_token.token)
    else:
        oura_token = ''
        existing_oura_token_str = ''

    # logger_users.info(f"--- POST (calling) Oura Ring (user: {current_user.id}) ---")
    # print('-- Oura Ring --')
    start_post_time = time.time()

    if request.method == 'POST':
        formDict = request.form.to_dict()
        logger_users.info(formDict)
        if current_user.id ==2:
            flash("Guest cannot change data. Register and then add data.", "info")
            return redirect(url_for('users.add_oura'))



        oura_token_user = sess.query(Oura_token).filter_by(user_id=current_user.id).first()
        if oura_token_user:
            logger_users.info(f"oura_token_user: {oura_token_user}")
            oura_token_id = oura_token_user.id

        if formDict.get('btn_link_oura'):

            startTime_post = time.time()
            # formDict = request.form.to_dict()
            new_token = formDict.get('oura_token_textbox')
            # new_location = formDict.get('location_text')
            # email = formDict.get('email')
            user = sess.query(Users).filter_by(id = current_user.id).first()
            yesterday = datetime.today() - timedelta(days=1)
            yesterday_formatted =  yesterday.strftime('%Y-%m-%d')



            #1) User adds Oura_token data
            if new_token != existing_oura_token_str:#<-- if new token is different
                logger_users.info('------ New token detected ------')
                #1-1a) if user has token replace it
                if existing_oura_token:
                    existing_oura_token.token = new_token
                    sess.commit()
                    oura_token_id = existing_oura_token.id
                    logger_users.info('One alrady exists ---> replace exisiting token')
                #1-1b) else add new token
                else:
                    print('Completely new token')
                    new_oura_token = Oura_token(user_id = current_user.id,
                        token = new_token)
                    sess.add(new_oura_token)
                    sess.commit()

                    oura_token_id = new_oura_token.id

                #1-1b-1) check if user has oura data yesterday
                oura_yesterday = sess.query(Oura_sleep_descriptions).filter_by(
                    user_id = current_user.id,
                    summary_date = yesterday_formatted).first()

                # --> 1-1b-1b) if no data yesterday, call API
                if not oura_yesterday and new_token != '':

                    if testing:# use local json file
                        json_utils_dir = r"/Users/nick/Documents/_testData/json_utils_dir_FromScheduler"
                        with open(os.path.join(json_utils_dir, '_oura2_call_oura_api.json')) as json_file:
                            sleep_dict = json.loads(json.load(json_file))

                        sleep_dict = sleep_dict.get(str(current_user.id))
                        logger_users.info(f"--- Adding oura data from Local json file ---")
                    else:# Make api call
                        sleep_dict = oura_sleep_call(new_token)



                    if isinstance(sleep_dict,dict):
                        sessions_added = oura_sleep_db_add(sleep_dict, oura_token_id)
                        flash(f'Successfully added {str(sessions_added)} sleep sesions and updated user Oura Token', 'info')
                    else:
                        logger_users.info(f'** Unable to get data from Oura API becuase {sleep_dict}')
                        flash(f'Unable to get data from Oura API becuase {sleep_dict}', 'warning')
                elif not new_token:
                    flash('User oura token successfully removed','info')
                    logger_users.info('** removed oura token from user')
                else:
                    logger_users.info('-- date detected yesterday for this user')
                    logger_users.info(oura_yesterday)



        elif formDict.get('recall_api'):
            if not existing_oura_token_str in ["", None]:
                logger_users.info('--- recall_api')
                if testing:# use local json file
                    json_utils_dir = r"/Users/nick/Documents/_testData/json_utils_dir_FromScheduler"
                    with open(os.path.join(json_utils_dir, '_oura2_call_oura_api.json')) as json_file:
                        sleep_dict = json.loads(json.load(json_file))

                    sleep_dict = sleep_dict.get(str(current_user.id))

                    logger_users.info(sleep_dict.keys())
                    logger_users.info(f"--- Adding oura data from Local json file ---")
                else:# Make api call
                    sleep_dict = oura_sleep_call(new_token)

                if isinstance(sleep_dict,dict):
                    sessions_added = oura_sleep_db_add(sleep_dict, oura_token_id)
                    flash(f'Successfully added {str(sessions_added)} sleep sesion(s)', 'info')
            else:
                flash(f"Must have a Oura Token", "warning")

        elif formDict.get('btn_delete_data'):
            logger_users.info('----> delete button pressed')
            # sleep_session_date_for_delete = "2022-10-23"
            delete_count = sess.query(Oura_sleep_descriptions).filter_by(user_id = current_user.id).delete()
            sess.query(Oura_token).filter_by(user_id=current_user.id).delete()
            sess.commit()
            logger_users.info('* successful delel;ete ')
            flash(f"Removed {delete_count} records", "warning")
        return redirect(url_for('users.add_oura'))

    return render_template('add_oura.html', oura_sleep_records = oura_sleep_records,
        oura_token = oura_token)



@users.route('/add_more_weather', methods=["GET","POST"])
def add_more_weather():
    return render_template('add_more_weather.html')








@users.route('/reset_password', methods = ["GET", "POST"])
def reset_password():
    page_name = 'Request Password Change'
    if current_user.is_authenticated:
        return redirect(url_for('dash.dashboard'))
    # form = RequestResetForm()
    # if form.validate_on_submit():
    if request.method == 'POST':
        formDict = request.form.to_dict()
        email = formDict.get('email')
        user = sess.query(Users).filter_by(email=email).first()
        if user:
        # send_reset_email(user)
            logger_users.info('Email reaquested to reset: ', email)
            send_reset_email(user)
            flash('Email has been sent with instructions to reset your password','info')
            # return redirect(url_for('users.login'))
        else:
            flash('Email has not been registered with What Sticks','warning')

        return redirect(url_for('users.reset_password'))
    return render_template('reset_request.html', page_name = page_name)


@users.route('/reset_password/<token>', methods = ["GET", "POST"])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('dash.dashboard'))
    user = Users.verify_reset_token(token)
    logger_users.info('user::', user)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('users.reset_password'))
    if request.method == 'POST':

        formDict = request.form.to_dict()
        if formDict.get('password_text') != '':
            hash_pw = bcrypt.hashpw(formDict.get('password_text').encode(), salt)
            user.password = hash_pw
            sess.commit()
            flash('Password successfully updated', 'info')
            return redirect(url_for('users.login'))
        else:
            flash('Must enter non-empty password', 'warning')
            return redirect(url_for('users.reset_token', token=token))

    return render_template('reset_request.html', page_name='Reset Password')


@users.route('/about_us')
def about_us():
    page_name = 'About us'
    return render_template('about_us.html', page_name = page_name)

@users.route('/privacy')
def privacy():
    page_name = 'Privacy'
    return render_template('privacy.html', page_name = page_name)

@users.route('/YouTube_OAuth_Cred_Request')
def youtube_request():
    page_name = 'YouTub OAuth 2.0 Credentials Request'
    return render_template('youtube.html', page_name = page_name)
