import argparse
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
        logger.info(
            f"Identified the latest approved model package: {model_package_arn}"
        )
        return model_package_arn
    except ClientError as e:
        error_message = e.response["Error"]["Message"]
        logger.error(error_message)
        raise Exception(error_message)


def extend_config(args, model_package_arn, stage_config):
    """
    Extend the stage configuration with additional parameters and tags based.
    """
    # Verify that config has parameters and tags sections
    if not "Parameters" in stage_config or not "StageName" in stage_config["Parameters"]:
        raise Exception("Configuration file must include SageName parameter")
    if not "Tags" in stage_config:
        stage_config["Tags"] = {}
    # Create new params and tags
    new_params = {
        "SageMakerProjectName": args.sagemaker_project_name,
        "ModelPackageName": model_package_arn,
        "ModelExecutionRoleArn": args.model_execution_role,
        "DataCaptureUploadPath": "s3://" + args.s3_bucket + '/datacapture-' + stage_config["Parameters"]["StageName"],
    }
    new_tags = {
        "sagemaker:deployment-stage": stage_config["Parameters"]["StageName"],
        "sagemaker:project-id": args.sagemaker_project_id,
        "sagemaker:project-name": args.sagemaker_project_name,
    }
    # Add tags from Project
    get_pipeline_custom_tags(args, sm_client, new_tags)

    return {
        "Parameters": {**stage_config["Parameters"], **new_params},
        "Tags": {**stage_config.get("Tags", {}), **new_tags},
    }

def get_pipeline_custom_tags(args, sm_client, new_tags):
    try:
        response = sm_client.describe_project(
            ProjectName=args.sagemaker_project_name
        )
        sagemaker_project_arn = response["ProjectArn"]
        response = sm_client.list_tags(
                ResourceArn=sagemaker_project_arn)
        project_tags = response["Tags"]
        for project_tag in project_tags:
            new_tags[project_tag["Key"]] = project_tag["Value"]
    except:
        logger.error("Error getting project tags")
    return new_tags

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


def add_model_package_name_to_yaml(template_path, model_package_arn):
    with open(template_path, "r") as file:
        template = yaml.safe_load(file)

    # Add ModelPackageName to the SageMakerModel Properties
    template["Resources"]["SageMakerModel"]["Properties"]["Containers"] = [
        {"ModelPackageName": model_package_arn}
    ]

    with open(template_path, "w") as file:
        yaml.dump(template, file, default_flow_style=False)


# Add environment variables to a SAM template
def add_environment_variables(template_path, function_name, variables):
    with open(template_path, "r") as file:
        template = yaml.safe_load(file)
    logger.info(f"variables: {variables}")
    print(template)
    print("function_name: ", function_name)
    print(template["Resources"])
    if "Resources" in template and function_name in template["Resources"]:
        function = template["Resources"][function_name]
        if "Properties" in function and "Environment" in function["Properties"]:
            function_env = function["Properties"]["Environment"]
            function_env.setdefault("Variables", {}).update(variables)
        else:
            function["Properties"]["Environment"] = {"Variables": variables}

    with open(template_path, "w") as file:
        yaml.dump(template, file, default_flow_style=False)

def get_cfn_style_config(stage_config):
    parameters = []
    for key, value in stage_config["Parameters"].items():
        parameter = {
            "ParameterKey": key,
            "ParameterValue": value
        }
        parameters.append(parameter)
    tags = []
    for key, value in stage_config["Tags"].items():
        tag = {
            "Key": key,
            "Value": value
        }
        tags.append(tag)
    return parameters, tags

def create_cfn_params_tags_file(config, export_params_file, export_tags_file):
    # Write Params and tags in separate file for Cfn cli command
    parameters, tags = get_cfn_style_config(config)
    with open(export_params_file, "w") as f:
        json.dump(parameters, f, indent=4)
    with open(export_tags_file, "w") as f:
        json.dump(tags, f, indent=4)


# Main execution
if __name__ == "__main__":
    # Argument parser setup
    parser = argparse.ArgumentParser(
        description="Add environment variables to the SAM template"
    )
    parser.add_argument(
        "--template-path",
        type=str,
        default="template.yml",
        help="Path to the SAM template file",
    )
    parser.add_argument("--function-name", type=str, help="Name of the Lambda function")
    parser.add_argument(
        "--log-level", type=str, default=os.environ.get("LOGLEVEL", "INFO").upper()
    )
    parser.add_argument("--model-execution-role", type=str, required=True)
    parser.add_argument("--model-package-group-name", type=str, required=True)
    parser.add_argument("--model-name", type=str, required=True)
    parser.add_argument("--sagemaker-project-id", type=str, required=True)
    parser.add_argument("--sagemaker-project-name", type=str, required=True)
    parser.add_argument("--s3-bucket", type=str, required=True)
    parser.add_argument("--import-staging-config", type=str, default="staging-config.json")
    parser.add_argument("--import-prod-config", type=str, default="prod-config.json")
    parser.add_argument("--export-staging-config", type=str, default="staging-config-export.json")
    parser.add_argument("--export-staging-params", type=str, default="staging-params-export.json")
    parser.add_argument("--export-staging-tags", type=str, default="staging-tags-export.json")
    parser.add_argument("--export-prod-config", type=str, default="prod-config-export.json")
    parser.add_argument("--export-prod-params", type=str, default="prod-params-export.json")
    parser.add_argument("--export-prod-tags", type=str, default="prod-tags-export.json")
    parser.add_argument("--export-cfn-params-tags", type=bool, default=False)
    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(args.log_level)

    # Fetch model package ARN
    logger.info("Getting model package ARN.")
    model_package_arn = get_approved_package(args.model_package_group_name)

    # Add the model package arn to the resource section
    add_model_package_name_to_yaml(args.template_path, model_package_arn)

    # Create dictionary of environment variables
    logger.info("Creating a dictionary of environment variables.")
    env_dict = {
        "MODEL_PACKAGE_ARN": model_package_arn,
        "MODEL_PACKAGE_GROUP_NAME": args.model_package_group_name,
        "MODEL_NAME": args.model_name,
        "SAGEMAKER_PROJECT_ID": args.sagemaker_project_id,
        "SAGEMAKER_PROJECT_NAME": args.sagemaker_project_name,
    }

    # Add environment variables to file
    logger.info(f"Adding environment variables to file: {args.template_path}")
    add_environment_variables(args.template_path, args.function_name, env_dict)

    # Write the staging config
    with open(args.import_staging_config, "r") as f:
        staging_config = extend_config(args, model_package_arn, json.load(f))
    logger.debug("Staging config: {}".format(json.dumps(staging_config, indent=4)))
    with open(args.export_staging_config, "w") as f:
        json.dump(staging_config, f, indent=4)
    if (args.export_cfn_params_tags):
      create_cfn_params_tags_file(staging_config, args.export_staging_params, args.export_staging_tags)

    # Write the prod config for code pipeline
    with open(args.import_prod_config, "r") as f:
        prod_config = extend_config(args, model_package_arn, json.load(f))
    logger.debug("Prod config: {}".format(json.dumps(prod_config, indent=4)))
    with open(args.export_prod_config, "w") as f:
        json.dump(prod_config, f, indent=4)
    if (args.export_cfn_params_tags):
      create_cfn_params_tags_file(prod_config, args.export_prod_params, args.export_prod_tags)

    with open(args.template_path, "r") as file:
        template = yaml.safe_load(file)

    logger.info("template.yml")
    logger.info(template)
