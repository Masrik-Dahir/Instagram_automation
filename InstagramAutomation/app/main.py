import json
from playwright.sync_api import sync_playwright
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
import logging
from datetime import datetime

S3_BUCKET_NAME = "masrikdahir-lambda"
S3_COOKIE_KEY = "InstagramAutomation/cookies.json"


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
        logging.info(f"Successfully wrote item to {table_name}: {item}")
        return response
    except ClientError as e:
        logging.error(f"Failed to write item to {table_name}: {e}")
        return None

def get_first_n_items(table_name, n, region_name='us-east-1'):
    dynamodb = boto3.resource('dynamodb', region_name=region_name)
    table = dynamodb.Table(table_name)

    items = []
    last_evaluated_key = None

    while len(items) < n:
        if last_evaluated_key:
            response = table.scan(
                ExclusiveStartKey=last_evaluated_key,
                Limit=n - len(items)
            )
        else:
            response = table.scan(Limit=n)

        items.extend(response.get('Items', []))
        last_evaluated_key = response.get('LastEvaluatedKey')

        if not last_evaluated_key:
            break

    return items[:n]


def delete_item_from_dynamodb(table_name, key, region_name='us-east-1'):
    dynamodb = boto3.resource('dynamodb', region_name=region_name)
    table = dynamodb.Table(table_name)

    try:
        response = table.delete_item(Key=key)
        return response
    except Exception as e:
        print(f"Error deleting item: {e}")
        return None


def get_secret(secret_name, region_name='us-east-1'):
    client = boto3.client('secretsmanager', region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)

        if 'SecretString' in response:
            return json.loads(response['SecretString'])
        else:
            return json.loads(response['SecretBinary'].decode('utf-8'))

    except ClientError as e:
        print(f"Error retrieving secret '{secret_name}': {e}")
        return None


def save_cookies(context):
    cookies = context.cookies()
    s3 = boto3.client("s3")

    try:
        cookie_data = json.dumps(cookies, indent=4).encode("utf-8")
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=S3_COOKIE_KEY, Body=cookie_data)
        logging.info("Cookies saved to S3.")
    except ClientError as e:
        logging.error(f"Failed to save cookies to S3: {e}")

def load_cookies(context):
    s3 = boto3.client("s3")

    try:
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=S3_COOKIE_KEY)
        content = response["Body"].read().decode("utf-8")
        cookies = json.loads(content)
        context.add_cookies(cookies)
        logging.info("Cookies loaded from S3.")
        return True
    except s3.exceptions.NoSuchKey:
        logging.warning("No cookie file in S3. Logging in fresh.")
        return False
    except (ClientError, json.JSONDecodeError) as e:
        logging.error(f"Failed to load cookies from S3: {e}")
        return False


def main():
    with sync_playwright() as p:
        # 1) Launch browser
        browser = p.chromium.launch(headless=False, slow_mo=300)

        # 2) Create a new browser context
        context = browser.new_context()
        isCookied = load_cookies(context)  # Load cookies from file if present
        print(f"Cookied: {str(isCookied)}")

        page = context.new_page()
        page.goto("https://www.instagram.com/masrikdahir/")  # Replace with your login URL

        if(not isCookied and page.is_visible("button:has-text('Log in')")):
            try:
                print("Logging in")
                username = get_secret("instagram_main")["username"]
                password = get_secret("instagram_main")["password"]

                # Fill out login form
                page.fill("input[name='username']", username)
                page.fill("input[name='password']", password)
                page.click("button[type='submit']")
                try:
                    page.wait_for_selector("text=Profile", timeout=10000)
                    page.goto("https://www.instagram.com/masrikdahir/")
                    print("Login successful. Found 'Masrik Dahir'. Saving cookies...")
                    save_cookies(context)
                except:
                    print("Error: Timed out waiting for 'Masrik Dahir'. Check the selector or credentials.")
                    write_item_to_dynamodb(
                        table_name="last_updated",
                        item={
                            "key": "InstagramAutomation",
                            "Result": "Unsuccessful - Profile Loading Timeout",
                            "Timestamp": datetime.utcnow().isoformat() + "Z"  # ISO 8601 format in UTC
                        }
                    )

                    return {
                        "statusCode": 500,
                        "body": json.dumps({
                            "message": "Timeout Error",
                        }),
                    }
            except:
                print("Error: They have blocked this IP")

                write_item_to_dynamodb(
                    table_name="last_updated",
                    item={
                        "key": "InstagramAutomation",
                        "Result": "Unsuccessful - Log In blocked",
                        "Timestamp": datetime.utcnow().isoformat() + "Z"  # ISO 8601 format in UTC
                    }
                )

                return {
                    "statusCode": 500,
                    "body": json.dumps({
                        "message": "Blocked IP",
                    }),
                }

        # 3) Check if the "Log in" button is visible (instead of checking page title)
        #    Adjust the selector for your actual "Log in" button text
        print("Already logged in via cookies.")
        print("Profile page:", page.content())


        # Dynamo Stuff
        links = [i["profile_link"] for i in get_first_n_items("instagram_unfollowers", 1000)]
        counter = 0
        for i in links:
            if counter >= 30:
                break
            try:
                page.goto(i)
                page.wait_for_selector("text=Following", timeout=5000)
                page.click("text=Following", timeout=5000)

                try:
                    page.wait_for_selector('div[role="dialog"]', timeout=5000)
                    page.click("text=Unfollow", timeout=5000)
                except:
                    pass

                print(delete_item_from_dynamodb(table_name="instagram_unfollowers",
                                                key={"profile_link": i}))
                print(f"Removed {i}")
                counter += 1
            except:
                if not page.is_visible("button:has-text('Log in')"):
                    print(delete_item_from_dynamodb(table_name="instagram_unfollowers",
                                                key={"profile_link": i}))
                print(f"Can't load {i}")
                pass

        # 5) Navigate to a page that requires login
        print("Profile page title:", page.title())

        # Close the browser
        browser.close()

    write_item_to_dynamodb(
        table_name="last_updated",
        item={
            "key": "InstagramAutomation",
            "Result": "Success",
            "Timestamp": datetime.utcnow().isoformat() + "Z"  # ISO 8601 format in UTC
        }
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Executed successfully",
        }),
    }

if __name__ == "__main__":
    main()
