import argparse
import json
import logging
import os
import yaml
import boto3
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger(__name__)
log_format = "%(levelname)s: [%(filename)s:%(lineno)s] %(message)s"
logging.basicConfig(format=log_format)

# AWS client setup
sm_client = boto3.client("sagemaker")


# Fetch latest approved model package for a model package group
def get_approved_package(model_package_group_name):
    try:
        # Fetch approved packages
        response = sm_client.list_model_packages(
            ModelPackageGroupName=model_package_group_name,
            ModelApprovalStatus="Approved",
            SortBy="CreationTime",
            MaxResults=100,
        )
        approved_packages = response["ModelPackageSummaryList"]

        # Fetch more packages if none returned with continuation token
        while len(approved_packages) == 0 and "NextToken" in response:
            response = sm_client.list_model_packages(
                ModelPackageGroupName=model_package_group_name,
                ModelApprovalStatus="Approved",
                SortBy="CreationTime",
                MaxResults=100,
                NextToken=response["NextToken"],
            )
            approved_packages.extend(response["ModelPackageSummaryList"])

        # Return error if no packages found
        if len(approved_packages) == 0:
            error_message = f"No approved ModelPackage found for ModelPackageGroup: {model_package_group_name}"
            logger.error(error_message)
            raise Exception(error_message)

        # Return model package ARN
        model_package_arn = approved_packages[0]["ModelPackageArn"]
        logger.info(f"Identified the latest approved model package: {model_package_arn}")
        return model_package_arn
    except ClientError as e:
        error_message = e.response["Error"]["Message"]
        logger.error(error_message)
        raise Exception(error_message)


# Custom constructor and representer for !Ref and !Sub tags
def ref_constructor(loader, node):
    value = loader.construct_scalar(node)
    return {"Ref": value}


def sub_constructor(loader, node):
    value = loader.construct_scalar(node)
    return {"Fn::Sub": value}


def sub_ref_representer(dumper, data):
    return dumper.represent_scalar("!Sub", data["Fn::Sub"])


def ref_ref_representer(dumper, data):
    return dumper.represent_scalar("!Ref", data["Ref"])


# Add constructors and representers to YAML loader and dumper
yaml.SafeLoader.add_constructor("!Ref", ref_constructor)
yaml.SafeLoader.add_constructor("!Sub", sub_constructor)
yaml.SafeDumper.add_representer(dict, sub_ref_representer)
yaml.SafeDumper.add_representer(dict, ref_ref_representer)


# Add environment variables to a SAM template
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


# Main execution
if __name__ == "__main__":
    # Argument parser setup
    parser = argparse.ArgumentParser(description="Add environment variables to the SAM template")
    parser.add_argument("--template_path", type=str, default="template.yml", help="Path to the SAM template file")
    parser.add_argument("--function_name", type=str, help="Name of the Lambda function")
    parser.add_argument("--log-level", type=str, default=os.environ.get("LOGLEVEL", "INFO").upper())
    parser.add_argument("--model-execution-role", type=str, required=True)
    parser.add_argument("--model-package-group-name", type=str, required=True)
    parser.add_argument("--sagemaker-project-id", type=str, required=True)
    parser.add_argument("--sagemaker-project-name", type=str, required=True)
    parser.add_argument("--s3-bucket", type=str, required=True)
    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(args.log_level)

    # Fetch model package ARN
    logger.info("Getting model package ARN.")
    model_package_arn = get_approved_package(args.model_package_group_name)

    # Create dictionary of environment variables
    logger.info("Creating a dictionary of environment variables.")
    env_dict = {
        "MODEL_PACKAGE_ARN": model_package_arn,
        "MODEL_PACKAGE_GROUP_NAME": args.model_package_group_name,
        "SAGEMAKER_PROJECT_ID": args.sagemaker_project_id,
        "SAGEMAKER_PROJECT_NAME": args.sagemaker_project_name,
    }

    # Add environment variables to file
    logger.info(f"Adding environment variables to file: {args.template_path}")
    add_environment_variables(args.template_path, args.function_name, env_dict)
