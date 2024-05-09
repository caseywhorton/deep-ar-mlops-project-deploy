# deep-ar-mlops-project-deploy

This repository contains code for an AWS-based pipeline that automates the creation and deployment of infrastructure necessary to run a Lambda function. This Lambda function executes a batch transform job against an approved model version hosted in Amazon SageMaker. The pipeline orchestrates the entire setup, leveraging AWS services to streamline the creation, configuration, and deployment of the infrastructure required for seamless execution.


## Overview

The pipeline utilizes AWS services to create and manage the following components:

+ Lambda Function: Executes batch transform jobs on SageMaker.
+ AWS SAM and CloudFormation: Defines the infrastructure resources.
+ Amazon SageMaker: Hosts the machine learning models.
+ Amazon CodeBuild & CodePipeline: Serverless compiling and deployment of code.

## Setup
### Prerequisites
Before setting up the pipeline, ensure you have:

+ AWS account credentials and permissions.
+ CodePipeline access and necessary IAM roles.
  
### Installation Steps  
+ Clone this repository.
+ Navigate to the AWS Management Console and set up the required permissions for CodePipeline, Lambda, and SageMaker.
+ Adjust the template.yml file to specify your Lambda function configurations and SageMaker model details.
+ Commit the changes and push them to your GitHub repository.
## Usage
### Pipeline Workflow
CodePipeline monitors the GitHub repository for changes.
Upon detecting a change, CodePipeline triggers the pipeline.
AWS CloudFormation creates or updates the necessary infrastructure based on the template.yml.
A Lambda function is deployed or updated in response to the pipeline execution.
The Lambda function can now run batch transform jobs against approved model versions in Amazon SageMaker.
## Directory Structure
```
├── weather/
|   ├── __init__.py
|   └── lambda.py
├── utils/
|   ├── __init__.py
|   └── preprocessing.py
├── .gitignore
├── afterAllowTraffic.js
├── beforeAllowTraffic.js
├── builder.py
├── buildspec.yml
├── template.yml
├── test/
│   ├── buildspec.yml
|   ├── test.py
└── README.md
```
### Committing Changes
When committing changes to this repository:

+ Make modifications to the necessary files, such as template.yml or the Lambda function code.
+ Use Git commands (git add ., git commit -m "Your commit message", git push origin main) to push changes to your repository.
+ Ensure meaningful commit messages that describe the changes made for better tracking.

# Resources
+ [AWS CodeBuild Documentation](https://docs.aws.amazon.com/codebuild/latest/userguide/welcome.html)
+ [AWS CodePipeline Documentation](https://docs.aws.amazon.com/codepipeline/latest/userguide/welcome.html)
+ [AWS Serverless Application Model](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)
+ [AWS CloudFormation Documentation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html)
+ [Amazon SageMaker Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/whatis.html)

## License
This project is licensed under the **MIT** License.
