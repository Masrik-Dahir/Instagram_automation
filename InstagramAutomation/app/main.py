import json
from playwright.sync_api import sync_playwright
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
import logging
from playwright_stealth import stealth_sync

S3_BUCKET_NAME = "masrikdahir-lambda"
S3_COOKIE_KEY = "InstagramAutomation/cookies.json"

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
        logging.info("✅ Cookies saved to S3.")
    except ClientError as e:
        logging.error(f"❌ Failed to save cookies to S3: {e}")

def load_cookies(context):
    s3 = boto3.client("s3")

    try:
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=S3_COOKIE_KEY)
        content = response["Body"].read().decode("utf-8")
        cookies = json.loads(content)
        context.add_cookies(cookies)
        logging.info("✅ Cookies loaded from S3.")
        return True
    except s3.exceptions.NoSuchKey:
        logging.warning("⚠️ No cookie file in S3. Logging in fresh.")
        return False
    except (ClientError, json.JSONDecodeError) as e:
        logging.error(f"❌ Failed to load cookies from S3: {e}")
        return False


def main():
    with sync_playwright() as p:
        # 1) Launch browser
        browser = p.chromium.launch(headless=False, slow_mo=300)

        # 2) Create a new browser context
        context = browser.new_context()
        load_cookies(context)  # Load cookies from file if present

        # 3) Open a new page
        page = context.new_page()
        page.goto("https://www.instagram.com/masrikdahir/")  # Replace with your login URL

        # 4) Check if the "Log in" button is visible (instead of checking page title)
        #    Adjust the selector for your actual "Log in" button text
        if page.is_visible("button:has-text('Log in')"):
            print("Log in button found. Need to log in.")

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
                print("Warning: Timed out waiting for 'Masrik Dahir'. Check the selector or credentials.")
        else:
            print("No 'Log in' button found. Likely already logged in via cookies.")

        # Dynamo Stuff
        links = [i["profile_link"] for i in get_first_n_items("instagram_unfollowers", 100)]
        for i in links[:20]:
            page.goto(i)
            page.wait_for_selector("text=Following", timeout=5000)
            page.click("text=Following", timeout=5000)

            try:
                page.wait_for_selector('div[role="dialog"]', timeout=5000)
                page.click("text=Unfollow", timeout=5000)
            except:
                None
            print(delete_item_from_dynamodb(table_name="instagram_unfollowers",
                                            key={"profile_link": i}))

        # 5) Navigate to a page that requires login
        print("Profile page title:", page.title())

        # Close the browser
        browser.close()

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Executed successfully",
        }),
    }

if __name__ == "__main__":
    main()
