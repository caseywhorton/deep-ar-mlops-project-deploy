import os
from datetime import datetime, timezone, timedelta
import pandas as pd
import boto3
from utils.preprocessing import featureDict, getStart, getStartString, columnNameReformat, preprocessQuant, dictToSeries, seriesToJSONline, roundUpHour
from params import WEATHER_FEATURES, ELECTRICITY_FEATURES, S3_SERVING_PREFIX_URI, S3_SERVING_INPUT_URI, S3_FORECAST_PREFIX_URI

def lambda_handler(event, context):
    try:
        # Initialize AWS clients
        s3 = boto3.client("s3")
        client = boto3.client("sagemaker")

        # Retrieve model name from environment variables
        model_name = os.environ.get("MODEL_NAME")
        print("Model name: {}".format(model_name))

        # Set S3 bucket and prefix
        bucket_weather_data = "cw-sagemaker-domain-1"
        bucket_electric_data = "cw-electric-demand-hourly-preprocessed"
        prefix = "deep_ar/data/raw"

        encoding = 'utf-8'

        # Get rolling calendar year of data
        day_window = 180
        today = datetime.now(timezone.utc)
        lag_days = datetime.now(timezone.utc) + timedelta(days=-day_window)

        # Get preprocessed weather data
        weather_df = get_preprocessed_data(s3, bucket_weather_data, prefix, today, lag_days)
        # Get preprocessed electric data
        objects = s3.list_objects(Bucket=bucket_electric_data, Prefix=prefix)
        df_list = []
        for o in objects["Contents"]:
            if o["LastModified"] <= today and o["LastModified"] >= lag_days:
                obj = s3.get_object(Bucket=bucket_electric_data, Key=o["Key"])
                df_list.append(pd.read_csv(obj["Body"]))
    
        electricity_df = pd.concat(df_list).drop_duplicates().reset_index()
        electricity_df.columns = [columnNameReformat(
            x) for x in electricity_df.columns]
        electricity_df.rename(columns={'period': 'timestamp'}, inplace=True)
        electricity_df.index = electricity_df.timestamp
        electricity_df.drop(['index', 'timestamp'], axis=1, inplace=True)

        # Merge weather and electricity data
        X = weather_df[WEATHER_FEATURES].merge(electricity_df[ELECTRICITY_FEATURES], how='inner', left_index=True, right_index=True)
        # Get the starting timestamp from the joined data
        start = getStart(X)

        # Preprocess the feature data
        time_series = [dictToSeries(featureDict(start_datetime=start, feature_data=preprocessQuant(X[feature]))) for feature in X.columns]

        # Write time series data to a JSONLines file
        file_name = "serving.json"
        with open("/tmp/" + file_name, "wb") as f:
            for ts in time_series:
                f.write(seriesToJSONline(ts, feature_name=list(ts.keys())[1]).encode(encoding))
                f.write("\n".encode(encoding))

        # Copy file to S3
        copy_to_s3("/tmp/" + file_name, S3_SERVING_PREFIX_URI + file_name, override=True)

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
                        "S3Uri": S3_SERVING_INPUT_URI,
                    }
                },
                "ContentType": "application/jsonlines",
                "CompressionType": "None",
                "SplitType": "None",
            },
            TransformOutput={
                "S3OutputPath": S3_FORECAST_PREFIX_URI,
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

def get_preprocessed_data(s3, bucket, prefix, today, lag_days):
    objects = s3.list_objects(Bucket=bucket, Prefix=prefix)
    df_list = []
    for o in objects["Contents"]:
        if o["LastModified"] <= today and o["LastModified"] >= lag_days:
            obj = s3.get_object(Bucket=bucket, Key=o["Key"])
            df_list.append(pd.read_csv(obj["Body"]))
    df = pd.concat(df_list).drop_duplicates().reset_index()
    df.columns = [columnNameReformat(x) for x in df.columns]
    df.timestamp = df.timestamp.apply(lambda x: roundUpHour(x))
    df.index = df.timestamp
    df.drop(['index', 'timestamp'], axis=1, inplace=True)
    return df

def copy_to_s3(local_path, s3_uri, override=False):
    s3 = boto3.resource('s3')
    bucket = s3_uri.split('/')[2]
    key = '/'.join(s3_uri.split('/')[3:])
    if not override:
        response = s3.meta.client.list_objects_v2(Bucket=bucket, Prefix=key)
        if response.get('Contents'):
            print(f"File {s3_uri} already exists in S3, skipping...")
            return
   
