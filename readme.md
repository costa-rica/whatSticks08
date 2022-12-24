
<img src="https://github.com/costa-rica/whatSticks08/blob/github-main/web/app_package/static/images/wshLogo_300px_doodle02.png?raw=true" alt="what sticks logo" width="200"/>

Visit current working web at:
https://what-sticks.com

## Description
What Sticks (WS) is an application that helps navigate your wellness with data already being collected by your other applications and devices.

Availible now to analyze your:
- Apple Health step count
- Oura Ring sleep quality
- Local weather

### Main Part of User Experience
There is a user dashboard that displays a table of correlations from your linked data. Here is an image of the steps dashboard

<img src="https://github.com/costa-rica/whatSticks08/blob/github-main/web/app_package/static/images/readme/stepsDashScreenShot.png?raw=true" alt="ws dash screenshot" width="500"/>


## Project/repo flow chart
<img src="https://github.com/costa-rica/whatSticks08/blob/github-main/web/app_package/static/images/readme/projectFlowChart.png?raw=true" alt="ws project flowchart" width="500"/>

This repo root folders contains:

- <b><font size=4>web</font></b>: Flask web application described in the description section.
- <b><font size=4>api</font></b>: used for processing large apple health files, scheduler and future mobile device application to communicate with database. 
- <b><font size=4>apple_services</font></b>: If the files are smaller than 100mb (uncompressed) then they are processed by the web application. Otherwise the web application hands off the large apple health file to the apple_services applications via API to process for database and prepare a pickle file used by the web application to display users data.
- <b><font size=4>scheduler</font></b>: this is a cron scheduler that sends out a call to collect weather and oura ring data for all users daily. Then updates the database. This keeps users data updated.



## Installation
This requires:
1. download/install ws_module (config and models) into your venv
2. config json file with api keys (I can provide if you contact me)
3. download this repo
4. python run from inside web/

### Step 1
Clone config and models packages from [whatSticks08modules](https://github.com/costa-rica/whatSticks08modules) repo.

```bash
git clone https://github.com/costa-rica/whatSticks08modules
```

:point_right: Important: Follow instructions for setting up environment in **whatSticks08modules**. 



### Step 2
Clone this repo
```bash
git clone https://github.com/costa-rica/whatSticks08
```

### Step 3
From inside whatSticks08/web activate ws08web venv
```bash
flask run
```
In a seperate terminal and from inside whatSticks08/api, activate ws08api venv
```bash
flask run --port=5001
```
#
## Once app is running

- First user to sign up is admin. There is an admin dashboard of all registered users so the admin can delete a user. No other users can see this dashboard. Admin can also write to blog.

- Second user use "Guest" with password "test"

- Login as Guest will then work showing the admin's dashboards but guest users won't be able to make any changes - only view.

- All other sign ups will have normal accounts that can add/remove their own data.
#
## Contributing
DM or email at whatsticks.com@gmail.com. 
I will send latest config.json file with api keys.

Very much welcome help but I would like to get to know you a little before I send keys. 

I am looking for help in these areas:
1. develop iOS application
2. frontend: make web app look pretty
3. backend help connecting to the different api's with OAuth 2.0
4. database
5. data science to improve metrics, data visulalizations, write articles on findings


## Thanks for reading!
:blush:
