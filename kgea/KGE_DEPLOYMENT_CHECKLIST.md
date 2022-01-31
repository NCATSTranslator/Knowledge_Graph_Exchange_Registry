# KGE Archive (AWS Production/Staging) Deployment Checklist

This document provides a fairly complete synopsis of the set of decisions and tasks to be completed in order to deploy a fresh installation of the KGE Archive application to the AWS cloud.

1. (AWS EC2 Dashboard) Decide on which AWS Region you wish to deploy the EC2, EBS, S3 and related resources for the system. Try to remain consistent in your choices (i.e. keep all such resources in the same AWS region and availability-zone).
2. (AWS EC2 Dashboard) Create EC2 instance (with suitable EBS) - with suitable parameters
3. (AWS EC2 Dashboard)Allocate and associate an Elastic IP
4. (ISP DNS) Map to create and point a selected hostname to EIP
5. (AWS EC2 Dashboard)Start and log into server using SSH and keypair
6. (EC2 server) Adjust any EBS volume boundaries
7. (EC2 server) Fix web server configuration:
    7.1 Fix nginx server configuration file to point https to hostname
        7.1.1 Change hostname
        7.1.2 Clean out any deprecated SSL/433 code but just- point to port 80
        7.1.3  Use certbot --nginx to add fresh SSL/433 for https://
8. (AWS Cognito Dashboard) Fix the AWS Cognito auth/auth config
    8.1 App Clients: create and configure new app client
    7.2 App Client Settings:
       7.2.1 Ensure that new app client Callback URL(s) and Sign out URL(s) are properly set to chosen hostname
       7.2.2 Enabled Identity Providers: Cognito User Pool
       7.2.3 OAuth 2.0: Allowed OAuth Flows: Authorization code grant;  Allowed OAuth Scopes:  email, openid, profile
9. (AWS S3 Dashboard) Fix the S3 bucket details
    9.1 Make sure that the bucket and primary subfolder (e.g. kge-data) exists; pay attention within which region the bucket is located
10. (EC2 server) Git clone/fetch/pull the desired code base into suitable location (e.g. /opt/projects/...)
    10.1 Fix the <KGE root code directory>kgea/config/config.yaml file:
        10.1.1 Fix the hostname
        10.1.2 Fix the client id and secret
        10.1.3 Fix the S3 parameters
        10.1.4 Adjust any other config.yaml parameters (if and as necessary or desired)
11. If you need to locally test components of the system outside the Docker containers, then ensure that required local OS level software is installed  (i.e. by 'sudo apt install...' etc. Refer to the KGEA_Archive_Dockerfile etc.) 
    - 11.1 apt-get update && apt-get upgrade -y && apt-get install -y build-essential git python-lxml nvme
    - 11.2 _Maybe create a local Python VENV and activate it..._
    - 11.3 python -m pip install --no-cache-dir -r requirements.txt
    - 11.4 curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"; unzip awscliv2.zip; ./aws/install; aws --version
12. (EC2 server) docker-compose launch (from KGE code root directory)
    - 12.1 docker-compose build
    - 12.2 docker-compose up -d
    - 12.3 docker image prune  # to clean out old images
    - 12.4 docker-compose logs -f  # to monitor the application
