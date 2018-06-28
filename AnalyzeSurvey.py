import requests
import zipfile
import json
import io
import os
import pandas as pd
import dropbox


def download_survey():
  # os.environ is reading environmental variables set in AWS Lambda configuration dashboard
  QUALTRICS_BASE_URL = 'https://' + os.environ['QUALTRICS_DATA_CENTER_ID'] + '/API/v3';
  RESPONSE_EXPORTS_URL = QUALTRICS_BASE_URL + '/responseexports/';

  # Setting user Parameters
  fileFormat = "csv"
  dataCenter = 'ca1'

  # Setting static parameters
  requestCheckProgress = 0
  progressStatus = "in progress"
  headers = {
      "content-type": "application/json",
      "x-api-token": os.environ['QUALTRICS_API_TOKEN'],
      }

  # Setting payload parameters
  downloadRequestPayload = '{"format":"' + fileFormat + '","surveyId":"' + os.environ['QUALTRICS_SURVEY_ID'] + '"}'

  # Step 1: Creating Data Export
  downloadRequestResponse = requests.request("POST", RESPONSE_EXPORTS_URL, data=downloadRequestPayload, headers=headers)
  progressId = downloadRequestResponse.json()["result"]["id"]
  print(' --- Step 1: Beginning Survey Export ---')
  print(downloadRequestResponse.text)
  downloadRequestCheckUrl = RESPONSE_EXPORTS_URL + progressId
  print(downloadRequestCheckUrl)

  # Step 2: Checking on Data Export Progress and waiting until export is ready
  while requestCheckProgress < 100 and progressStatus is not "complete":
      requestCheckResponse = requests.request("GET", downloadRequestCheckUrl, headers=headers)
      requestCheckProgress = requestCheckResponse.json()["result"]["percentComplete"]
      print(' --- Step 2: Survey Export is ' + str(requestCheckProgress) + ' complete ---')

  # Step 3: Downloading file
  surveyFileDownloadUrl = RESPONSE_EXPORTS_URL + progressId + '/file'
  requestDownload = requests.request("GET", surveyFileDownloadUrl, headers=headers, stream=True)
  print(' --- Step 3: Survey Download Complete ---')


  os.chdir('/tmp')  # IMPORTANT: this is needed because AWS Lambda can write files only to /tmp folder

  # Step 4: Unzipping the file
  zipfile.ZipFile(io.BytesIO(requestDownload.content)).extractall("MyQualtricsDownload")
  print(' --- Step 4: Survey File Extracted to /tmp ---')


def compute_scores():
  # CONSTANTS FOR SURVEY SCORES COMPUTATION
  max_option_score = 4

  people_qn_count = 8
  process_qn_count = 7
  place_qn_count = 4

  max_people_score  = people_qn_count  * max_option_score
  max_process_score = process_qn_count * max_option_score
  max_place_score   = place_qn_count   * max_option_score

  max_total_score = max_people_score + max_process_score + max_place_score

  survey = pd.read_csv("MyQualtricsDownload/Prework Survey - TestGround.csv", skiprows=[1,2])

  # Step 5a: Computing individual scores
  survey["RawPeopleScore"] = survey["6"] + survey["7"] + survey["8"] + survey["9"] + survey["10"] + survey["11"] + survey["12"] + survey["13"]
  survey["RawProcessScore"] = survey["14"] + survey["15"] + survey["16"] + survey["17"] + survey["18"] + survey["19"] + survey["20"]
  survey["RawPlaceScore"] = survey["21"] + survey["22"] + survey["23"] + survey["24"]
  survey["RawTotalScore"] = survey["RawPeopleScore"] + survey["RawProcessScore"] + survey["RawPlaceScore"]

  survey["PeoplePercent"]  = survey["RawPeopleScore"]  / max_people_score * 100
  survey["ProcessPercent"] = survey["RawProcessScore"] / max_people_score * 100
  survey["PlacePercent"]   = survey["RawPlaceScore"]   / max_people_score * 100
  survey["TotalPercent"]   = survey["RawTotalScore"]   / max_total_score  * 100

  # Step 5b: Computing team scores (6.1 refers to team id in Qualtrics survey)
  team_survey_avgs = survey.groupby(['6.1'])["RawPeopleScore", "PeoplePercent","RawProcessScore", "ProcessPercent", "RawPlaceScore", "PlacePercent", "RawTotalScore", "TotalPercent"].mean()

  # Step 5b: Computing team scores
  survey.to_csv('all_people_scores.csv')
  team_survey_avgs.to_csv('team_average_scores.csv')
  print(' --- Step 5: Survey Analysis Complete ---')


def upload_to_dropbox():
  print(' --- Step 6: Beginning analysis upload to Dropbox ---')
  dbx = dropbox.Dropbox(os.environ['DROPBOX_ACCESS_TOKEN'])

  file_from = 'all_people_scores.csv'
  file_to = '/ddt/all_people_scores.csv'  # The full path to upload the file to, including the file name
  with open(file_from, 'rb') as f:
      dbx.files_upload(f.read(), file_to, mode=dropbox.files.WriteMode('overwrite'))
  print(' --- Step 6a: Individual analysis upload COMPLETE ---')

  file_from = 'team_average_scores.csv'
  file_to = '/ddt/team_average_scores.csv'  # The full path to upload the file to, including the file name
  with open(file_from, 'rb') as f:
      dbx.files_upload(f.read(), file_to, mode=dropbox.files.WriteMode('overwrite'))
  print(' --- Step 6b: Team analysis upload COMPLETE ---')



def lambda_handler(event, context):
  # Step 1 - 4: Download survey
  download_survey()

  # Step 5: Analyzing the survey
  compute_scores()

  # Step 6: Upload files to Dropbox
  upload_to_dropbox()

  return {'returnValue':'method worked!'}


