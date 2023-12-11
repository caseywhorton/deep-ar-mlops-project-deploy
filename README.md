# AWS Pipeline for Lambda Function Batch Transform Job
This repository contains code for an AWS-based pipeline that automates the creation and deployment of infrastructure necessary to run a Lambda function executing a batch transform job against an approved model version in Amazon SageMaker.

## Overview
The pipeline utilizes AWS services to create and manage the following components:

+ Lambda Function: Executes batch transform jobs on SageMaker.
+ AWS CloudFormation: Defines the infrastructure resources.
+ Amazon SageMaker: Hosts the machine learning models.

## Setup
### Prerequisites
Before setting up the pipeline, ensure you have:

+ AWS account credentials and permissions.
+ CodePipeline access and necessary IAM roles.
Installation Steps
Clone this repository.
Navigate to the AWS Management Console and set up the required permissions for CodePipeline, Lambda, and SageMaker.
Adjust the template.yml file to specify your Lambda function configurations and SageMaker model details.
Commit the changes and push them to your GitHub repository.
Usage
Pipeline Workflow
CodePipeline monitors the GitHub repository for changes.
Upon detecting a change, CodePipeline triggers the pipeline.
AWS CloudFormation creates or updates the necessary infrastructure based on the template.yml.
Lambda function is deployed or updated in response to the pipeline execution.
The Lambda function can now run batch transform jobs against approved model versions in Amazon SageMaker.
Folder Structure
LambdaFunction: Contains the Lambda function code and configurations.
InfrastructureAsCode: Holds the CloudFormation template for defining the infrastructure.
Committing Changes
When committing changes to this repository:

Make modifications to the necessary files, such as template.yml or the Lambda function code.
Use Git commands (git add ., git commit -m "Your commit message", git push origin main) to push changes to your repository.
Ensure meaningful commit messages that describe the changes made for better tracking.
Resources
AWS CodePipeline Documentation
AWS CloudFormation Documentation
Amazon SageMaker Documentation
License
This project is licensed under the MIT License.

