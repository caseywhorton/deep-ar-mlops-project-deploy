import argparse
import json
import logging
import os
import yaml
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
log_format = "%(levelname)s: [%(filename)s:%(lineno)s] %(message)s"
logging.basicConfig(format=log_format)

sm_client = boto3.client("sagemaker")

def get_approved_package(model_package_group_name):
    try:
        response = sm_client.list_model_packages(
            ModelPackageGroupName=model_package_group_name,
            ModelApprovalStatus="Approved",
            SortBy="CreationTime",
            MaxResults=100,
        )
        approved_packages = response["ModelPackageSummaryList"]

        while len(approved_packages) == 0 and "NextToken" in response:
            response = sm_client.list_model_packages(
                ModelPackageGroupName=model_package_group_name,
                ModelApprovalStatus="Approved",
                SortBy="CreationTime",
                MaxResults=100,
                NextToken=response["NextToken"],
            )
            approved_packages.extend(response["ModelPackageSummaryList"])

        if len(approved_packages) == 0:
            error_message = f"No approved ModelPackage found for ModelPackageGroup: {model_package_group_name}"
            logger.error(error_message)
            raise Exception(error_message)

        model_package_arn = approved_packages[0]["ModelPackageArn"]
        logger.info(f"Identified the latest approved model package: {model_package_arn}")
        return model_package_arn
    except ClientError as e:
        error_message = e.response["Error"]["Message"]
        logger.error(error_message)
        raise Exception(error_message)

def add_model_package_name_to_yaml(template_path, model_package_arn):
    with open(template_path, "r") as file:
        template = yaml.safe_load(file)

    template['Resources']['SageMakerModel']['Properties']['Containers'] = [
        {'ModelPackageName': model_package_arn}
    ]

    with open(template_path, "w") as file:
        yaml.dump(template, file, default_flow_style=False)

def add_environment_variables(template_path, function_name, variables):
    with open(template_path, "r") as file:
        template = yaml.safe_load(file)

    if "Resources" in template and function_name in template["Resources"]:
        function = template["Resources"][function_name]
        if "Properties" in function and "Environment" in function["Properties"]:
            function_env = function["Properties"]["Environment"]
            function_env.setdefault("Variables", {}).update(variables)
        else:
            function["Properties"]["Environment"] = {"Variables": variables}
    
    with open(template_path, "w") as file:
        yaml.dump(template, file, default_flow_style=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add environment variables to the SAM template")
    parser.add_argument("--template-path", type=str, default="template.yml", help="Path to the SAM template file")
    parser.add_argument("--function-name", type=str, help="Name of the Lambda function")
    parser.add_argument("--log-level", type=str, default=os.environ.get("LOGLEVEL", "INFO").upper())
    parser.add_argument("--model-execution-role", type=str, required=True)
    parser.add_argument("--model-package-group-name", type=str, required=True)
    parser.add_argument("--model-name", type=str, required=True)
    parser.add_argument("--sagemaker-project-id", type=str, required=True)
    parser.add_argument("--sagemaker-project-name", type=str, required=True)
    parser.add_argument("--s3-bucket", type=str, required=True)
    args = parser.parse_args()

    logging.getLogger().setLevel(args.log_level)

    logger.info("Getting model package ARN.")
    model_package_arn = get_approved_package(args.model_package_group_name)
    add_model_package_name_to_yaml(args.template_path, model_package_arn)

    logger.info("Creating a dictionary of environment variables.")
    env_dict = {
        "MODEL_PACKAGE_ARN": model_package_arn,
        "MODEL_PACKAGE_GROUP_NAME": args.model_package_group_name,
        "MODEL_NAME": args.model_name,
        "SAGEMAKER_PROJECT_ID": args.sagemaker_project_id,
        "SAGEMAKER_PROJECT_NAME": args.sagemaker_project_name,
    }

    logger.info(f"Adding environment variables to file: {args.template_path}")
    add_environment_variables(args.template_path, args.function_name, env_dict)
    
    with open(args.template_path, "r") as file:
        template = yaml.safe_load(file)
        
    logger.info("template.yml")
    logger.info(template)
