import os
import json
import boto3
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def lambda_handler(event, context):

    return {
        "statusCode": 200,
        "body": json.dumps({
            "success"
        })
    }