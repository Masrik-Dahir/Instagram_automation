import os
import json
import boto3
import zipfile
import json
import os
import tempfile
import logging
from datetime import datetime

s3 = boto3.client('s3')


def write_item_to_dynamodb(table_name, item, region_name='us-east-1'):
    """
    Write an item to a DynamoDB table.

    :param table_name: Name of the DynamoDB table
    :param item: A dictionary representing the item to write
    :param region_name: AWS region (default: us-east-1)
    :return: Response from DynamoDB or None on error
    """
    dynamodb = boto3.resource('dynamodb', region_name=region_name)
    table = dynamodb.Table(table_name)

    try:
        response = table.put_item(Item=item)
        logging.info(f"✅ Successfully wrote item to {table_name}: {item}")
        return response
    except ClientError as e:
        logging.error(f"❌ Failed to write item to {table_name}: {e}")
        return None


def extract_unfollowers_from_zip(zip_path):
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        folder = os.path.join(temp_dir, 'connections', 'followers_and_following')
        following_hrefs = set()
        followers_hrefs = set()

        # Collect all following*.json and followers*.json files
        for file_name in os.listdir(folder):
            full_path = os.path.join(folder, file_name)
            if file_name.startswith('following') and file_name.endswith('.json'):
                with open(full_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get('relationships_following', []):
                        hrefs = [entry['href'] for entry in item.get('string_list_data', [])]
                        following_hrefs.update(hrefs)

            elif file_name.startswith('followers') and file_name.endswith('.json'):
                with open(full_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        hrefs = [entry['href'] for entry in item.get('string_list_data', [])]
                        followers_hrefs.update(hrefs)

        # Return following hrefs that are not in followers
        return list(following_hrefs - followers_hrefs)


def lambda_handler(event, context):
    try:
        try:
            # Extract bucket name and object key from event
            bucket_name = event['Records'][0]['s3']['bucket']['name']
            object_key = event['Records'][0]['s3']['object']['key']
        except e:
            logging.error(f"❌ Unable to get data from S3: {e}")
            return {
                'statusCode': 500,
                'body': "❌ Unable to get data from S3"
            }

        # Download zip file to /tmp
        local_zip_path = f'/tmp/{os.path.basename(object_key)}'
        s3.download_file(bucket_name, object_key, local_zip_path)
        unfollowers = extract_unfollowers_from_zip(local_zip_path)

        try:
            for unfollower in unfollowers:
                try:
                    write_item_to_dynamodb(
                        table_name="instagram_unfollowers",
                        item={
                            "profile_link": unfollower
                        }
                    )
                except e:
                    logging.error(
                        f"❌ Unable to write to DynamoDB table {'instagram_unfollowers'}, item {unfollower}: {e}")
                    return {
                        'statusCode': 500,
                        'body': "❌ Unable to write to DynamoDB"
                    }

            write_item_to_dynamodb(
                table_name="last_updated",
                item={
                    "key": "InstagramRawProcessor",
                    "Result": "Success",
                    "Timestamp": datetime.utcnow().isoformat() + "Z"  # ISO 8601 format in UTC
                }
            )
        except e:
            logging.error(
                f"❌ Unable to write to DynamoDB table {'last_updated'}, item {'InstagramRawProcessor'}: {e}")
            return {
                'statusCode': 500,
                'body': "❌ Unable to write to DynamoDB"
            }

        # Delete file from S3 after processing
        try:
            s3.delete_object(Bucket=bucket_name, Key=object_key)
            logging.info(f"🗑️ Successfully deleted {object_key} from bucket {bucket_name}")
        except Exception as e:
            logging.error(f"❌ Failed to delete {object_key} from S3: {e}")

        # Process zip file
        logging.error(f"✅ Success")
        return {
            'statusCode': 200,
            'body': "✅ Success"
        }
    except e:
        logging.error(f"❌ Unable to parse json for unfollowers: {e}")
        return {
            'statusCode': 500,
            'body': "❌ Unable to parse json for unfollowers"
        }
