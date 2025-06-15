# 📸 Instagram Automation

Automate Instagram interactions using AWS Lambda, Docker, and ECS Fargate.

---

## 🚀 First-Time Setup

Before deployment, delete the default SAM stack if it exists:

```bash
sam delete --stack-name aws-sam-cli-managed-default
```

---

## 🛠 Build and Deploy

### Basic Deployment

```bash
sam build --no-cached
sam deploy --guided
```

### Build with Container Support

```bash
sam build --use-container
```

---

## 🐳 Docker & ECR Setup

### 1. Create ECR Repository

```bash
aws ecr create-repository --repository-name instagram-automation
```

Sample output:

```json
{
  "repository": {
    "repositoryArn": "arn:aws:ecr:us-east-1:<account-id>:repository/instagram-automation",
    "registryId": "<account-id>",
    "repositoryName": "instagram-automation",
    "repositoryUri": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/instagram-automation",
    "createdAt": "2025-06-14T11:00:48.320000-04:00",
    "imageTagMutability": "MUTABLE",
    "imageScanningConfiguration": {
      "scanOnPush": false
    },
    "encryptionConfiguration": {
      "encryptionType": "AES256"
    }
  }
}
```

### 2. Authenticate Docker to ECR

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

#### 💡 Windows Fix (if login fails)

If you see this error:

```bash
Error saving credentials: error storing credentials - err: exit status 1, out: `Not enough memory resources are available to process this command.`
```

✅ **Fix**:

- Open **Credential Manager** (Search “Windows Credential Manager”)
- Go to **Windows Credentials** tab
- Backup credentials (optional) and remove excessive/unnecessary entries (e.g., from Adobe)

---

### 3. Build, Tag & Push Docker Image

```bash
docker buildx build --platform linux/amd64 -t instagram-automation .\InstagramAutomation\ --load
docker tag instagram-automation:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/instagram-automation:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/instagram-automation:latest
```

---

## 🖥 ECS Task Deployment

```bash
aws ecs register-task-definition --cli-input-json file://InstagramAutomation/task-definition.json
```

```bash
aws ecs run-task \
  --region us-east-1 \
  --cluster default \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<subnet>],securityGroups=[<securityGroup>],assignPublicIp=ENABLED}" \
  --task-definition ecs-instagram-automation-task
```

---

## 🧪 Local Run

```bash
docker build -t instagram-automation .\InstagramAutomation\
```

```bash
docker run \
  -ti --init \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e AWS_DEFAULT_REGION=us-east-1 \
  instagram-automation
```
