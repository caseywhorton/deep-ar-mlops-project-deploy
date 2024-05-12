import os
from datetime import datetime, timezone, timedelta
import pandas as pd
import boto3
from utils.preprocessing import getStart, getStartString, featureDict, columnNameReformat, preprocessQuant, dictToSeries, seriesToJSONline
from params import FEATURES, S3_SERVING_PREFIX_URI, S3_SERVING_INPUT_URI, S3_FORECAST_PREFIX_URI


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

        electricity_features = ['value_demand']
        weather_features = ['temperature_value', 'relativehumidity_value']

        encoding = 'utf-8'

        # Get rolling calendar year of data
        day_window = 180
        today = datetime.now(timezone.utc)
        lag_days = datetime.now(timezone.utc) + timedelta(days=-day_window)

         # get preprocessed weather data
        objects = s3.list_objects(Bucket=bucket_weather_data, Prefix=prefix)
    
        df_list = []
        for o in objects["Contents"]:
            if o["LastModified"] <= today and o["LastModified"] >= lag_days:
                obj = s3.get_object(Bucket=bucket_weather_data, Key=o["Key"])
                df_list.append(pd.read_csv(obj["Body"]))
    
        weather_df = pd.concat(df_list).drop_duplicates().reset_index()
        weather_df.columns = [columnNameReformat(x) for x in weather_df.columns]
        weather_df.timestamp = weather_df.timestamp.apply(
            lambda x: roundUpHour(x))
        weather_df.index = weather_df.timestamp
        weather_df.drop(['index', 'timestamp'], axis=1, inplace=True)
    
        # get preprocessed electric data
    
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
    
        X = weather_df[weather_features].merge(
            electricity_df[electricity_features], how='inner', left_index=True, right_index=True)
        # get the starting timestamp from the joined data
        start = start_str = getStart(X)
        print(start)
    
        # preprocess the feature data
        mylist = list()
    
        # should only be the target columns
        for feature in X.columns:
            mylist.append(
                featureDict(
                    start_datetime=start_str,
                    feature_data=preprocessQuant(X[feature]),
                )
            )
    
        # create the individual time series for each feature
        time_series = []
        for i in mylist:
            time_series.append(dictToSeries(i))
    
        # Write time series data to a JSONLines file
        encoding = "utf-8"
        file_name = "serving.json"
        with open("/tmp/" + file_name, "wb") as f:
            for i, ts in enumerate(time_series):
                f.write(
                    seriesToJSONline(
                        ts, feature_name=list(mylist[i].keys())[1]
                    ).encode(encoding)
                )
                f.write("\n".encode(encoding))

        # Copy file to S3
        copy_to_s3(
            "/tmp/" + file_name,
            S3_SERVING_PREFIX_URI + file_name,
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
        try:
            buk.put_object(Key=path, Body=data)
        except:
            print("could not put object to s3")
