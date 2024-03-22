import os
from datetime import datetime, timezone, timedelta
import pandas as pd
import boto3
from utils.preprocessing import getStart, getStartString, featureDict, columnNameReformat, preprocessQuant, dict_to_series, series_to_jsonline
from params import FEATURES, S3_SERVING_PREVIX_URL, S3_SERVING_INPUT_URL, S3_FORECAST_OUTPUT_URL


def lambda_handler(event, context):
    try:
        # Initialize AWS clients
        s3 = boto3.client("s3")
        client = boto3.client("sagemaker")

        # Retrieve model name from environment variables
        model_name = os.environ.get("MODEL_NAME")
        print("Model name: {}".format(model_name))

        # Set S3 bucket and prefix
        bucket = "cw-sagemaker-domain-1"
        prefix = "deep_ar/data/raw"

        # Get rolling calendar year of data
        today = datetime.now(timezone.utc)
        lag_365 = datetime.now(timezone.utc) + timedelta(days=-365)

        # List objects in S3 bucket
        objects = s3.list_objects(Bucket=bucket, Prefix=prefix)["Contents"]

        df_list = []
        for o in objects:
            if lag_365 <= o["LastModified"] <= today:
                obj = s3.get_object(Bucket=bucket, Key=o["Key"])
                df_list.append(pd.read_csv(obj["Body"]))

        # Concatenate dataframes, drop duplicates, and reset index
        preprocessed_df = pd.concat(df_list).drop_duplicates().reset_index()

        # Get start date from preprocessed data's index
        start = getStart(preprocessed_df)
        start_str = getStartString(preprocessed_df)

        # Process features
        mylist = []
        for feature in FEATURES:
            mylist.append(
                featureDict(
                    start_str,
                    columnNameReformat(feature, "properties.relativeHumidity.value"),
                    preprocessQuant(preprocessed_df[feature]),
                )
            )

        # Convert feature dictionaries to time series
        time_series = [dict_to_series(i) for i in mylist]

        # Write time series data to a JSONLines file
        encoding = "utf-8"
        file_name = "serving.json"
        with open("/tmp/" + file_name, "wb") as f:
            for i, ts in enumerate(time_series):
                f.write(
                    series_to_jsonline(
                        ts, feature_name=list(mylist[i].keys())[1]
                    ).encode(encoding)
                )
                f.write("\n".encode(encoding))

        # Copy file to S3
        copy_to_s3(
            "/tmp/" + file_name,
            "s3://cw-weather-data-deployment/serving/" + file_name,
            override=True,
        )

        # Create a timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

        # Create the TransformJobName with a timestamp
        transform_job_name = f"WeatherBatchTransform-{timestamp}"

        # Create transform job
        response = client.create_transform_job(
            TransformJobName=transform_job_name,
            ModelName=model_name,
            MaxConcurrentTransforms=1,
            ModelClientConfig={
                "InvocationsTimeoutInSeconds": 600,
                "InvocationsMaxRetries": 3,
            },
            MaxPayloadInMB=30,
            BatchStrategy="SingleRecord",
            TransformInput={
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": "s3://cw-weather-data-deployment/serving/serving.json",
                    }
                },
                "ContentType": "application/jsonlines",
                "CompressionType": "None",
                "SplitType": "None",
            },
            TransformOutput={
                "S3OutputPath": "s3://cw-weather-data-deployment/forecasts/",
                "Accept": "application/jsonlines",
                "AssembleWith": "Line",
            },
            TransformResources={
                "InstanceType": "ml.m5.xlarge",
                "InstanceCount": 1,
            },
        )

    except Exception as e:
        print(e)
        raise e

    return {"statusCode": 200, "body": "Lambda execution completed"}

def copy_to_s3(local_file, s3_path, override=False):
    s3 = boto3.resource("s3")
    assert s3_path.startswith("s3://")
    split = s3_path.split("/")
    bucket = split[2]
    path = "/".join(split[3:])
    buk = s3.Bucket(bucket)
    if len(list(buk.objects.filter(Prefix=path))) > 0:
        if not override:
            print(
                "File s3://{}/{} already exists.\nSet override to upload anyway.\n".format(
                    bucket, s3_path
                )
            )
            return
        else:
            print("Overwriting existing file")
    with open(local_file, "rb") as data:
        print("Uploading file to {}".format(s3_path))
        try:
            buk.put_object(Key=path, Body=data)
        except:
            print("could not put object to s3")
