import pandas as pd
import numpy as np
import json
import boto3
from typing import Dict, List
from datetime import datetime, timedelta


def columnNameReformat(column_name: str, target_name: str = None) -> str:
    """Reformats a column name for easier use in applications."""
    column_name = column_name.lower()
    column_name = column_name.replace("properties.", "")
    column_name = column_name.replace(".", "_").replace(" ", "_")
    column_name = column_name.strip()
    return column_name


def roundUpHour(datetime_str: str):
    "Rounds a timestamp up to next nearest hour."
    # Convert datetime string to a datetime object
    dt = datetime.fromisoformat(datetime_str)

    # Round up to the nearest hour
    rounded_dt = dt + timedelta(hours=1) - \
        timedelta(minutes=dt.minute, seconds=dt.second)
    rounded_dt = rounded_dt.replace(
        minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")

    return rounded_dt


def getCloudCover(x):
    try:
        return x[0]["amount"]
    except Exception as e:
        return e


def preprocessElectricHourlyDemandJSON(data):
    "Preprocesses the electric demand data into a dataframe."
    # read dataframe from json for URL response data
    df = pd.DataFrame(data['response']['data'])
    # pivot from short to long
    pivot_df = df.pivot(index=[
                        'period', 'respondent', 'value-units'],
                        columns=['type-name'], values=['value'])
    # collapse value column names
    pivot_df.columns = ['_'.join(col) for col in pivot_df.columns.values]
    # reset the index, get rid of multi-index

    pivot_df = pivot_df.reset_index()
    # clean up the column names
    pivot_df.columns = [x.replace('-', '_').lower().strip()
                        for x in pivot_df.columns]

    # transform the timestamp from UTC (e.g. '2024-03-01T00') formatting to
    #  "%Y-%m-%d %H:%M:%S"
    pivot_df.period = pivot_df.period.apply(
        lambda x: pd.to_datetime(x, utc=True).strftime("%Y-%m-%d %H:%M:%S"))

    # apply some final cleaning/preparation
    pivot_df = pivot_df.sort_values(by='period')
    pivot_df = pivot_df.drop_duplicates()
    pivot_df.index = pivot_df.period
    pivot_df = pivot_df.drop('period', axis=1)

    return pivot_df


def cleanRawWeatherJSON(raw_json, weather_station_url: str = "https://api.weather.gov/stations/KCVG"):
    """
    Cleans the raw JSON object into a DataFrame.
    """
    # Normalize the JSON and filter by the specified weather station URL
    df = pd.json_normalize(raw_json, record_path="features")
    df = df[df["properties.station"] == weather_station_url]

    # Set the index to the timestamp and sort the DataFrame
    df.index = df["properties.timestamp"]
    df.sort_index(inplace=True)

    # Select relevant features and drop duplicate rows
    # Define your features here
    features = ["feature1", "feature2", "feature3"]
    df = df[["properties.timestamp"] + features].drop_duplicates()

    return df


def preprocessQuant(feature) -> np.array:
    """Processes a quantiative feature for input to an ML algorithm"""
    x = np.array(feature)
    np.nan_to_num(x, copy=False)
    return x


def featureDict(start_datetime: datetime, feature_data: List) -> Dict:
    """Creates a python Dict object for a feature with a given start date."""
    return {
        "start": start_datetime,
        "target": feature_data.reshape(1, len(feature_data))[0].tolist(),
    }


def getStart(df: pd.DataFrame) -> str:
    """Gets the start date for the input data from the dataframe."""
    return df.index[0]


def getStartString(
        df: pd.DataFrame, timestamp_column: str = "timestamp") -> str:
    """Gets the start date in a string format"""
    stp = datetime.strptime(df[timestamp_column]
                            [0], "%Y-%m-%dT%H:%M:%S%z")
    return datetime.strftime(stp, "%Y-%m-%d %H:%M:%S")


def preprocessWeatherDataFrame(df: pd.DataFrame) -> pd.DataFrame:
    """Processes the dataframe."""
    stp = df["properties.timestamp"].apply(
        lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S%z")
    )
    df.index = stp
    df.sort_index(inplace=True)
    df.index.name = "timestamp"
    return df


def writeDictsToFile(path, data):
    with open(path, "wb") as fp:
        for d in data:
            fp.write(json.dumps(d).encode("utf-8"))
            fp.write("\n".encode("utf-8"))


def seriesToObj(ts, feature_name=None, cat=None):
    obj = {"start": str(ts.index[0]), feature_name: list(ts)}
    if cat is not None:
        obj["cat"] = cat
    return obj


def seriesToJSONline(ts, feature_name=None, cat=None):
    return json.dumps(seriesToObj(ts, feature_name, cat))


def dictToSeries(time_dict: dict) -> pd.Series:
    "Translates a dictionary to a time series using a pandas series data type."
    time_index = pd.date_range(
        start=time_dict["start"], periods=len(list(time_dict.values())[1]),
        freq="H"
    )
    time_index = [x.strftime("%Y-%m-%d %H:%M:%S") for x in time_index]
    return pd.Series(data=list(time_dict.values())[1], index=time_index)


def getPreprocessedWeatherData(s3, bucket, prefix, today, lag_days):
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
    
def getPreprocessedElectricityData(s3, bucket, prefix, today, lag_days):
    objects = s3.list_objects(Bucket=bucket, Prefix=prefix)
    df_list = []
    for o in objects["Contents"]:
        if o["LastModified"] <= today and o["LastModified"] >= lag_days:
            obj = s3.get_object(Bucket=bucket, Key=o["Key"])
            df_list.append(pd.read_csv(obj["Body"]))

    df = pd.concat(df_list).drop_duplicates().reset_index()
    df.columns = [columnNameReformat(
        x) for x in df.columns]
    df.rename(columns={'period': 'timestamp'}, inplace=True)
    df.index = df.timestamp
    df.drop(['index', 'timestamp'], axis=1, inplace=True)
    return df

def copyToS3(local_file, s3_path, override=False):
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
        except Exception as e:
            print(f"could not put object to s3 {str(e)}")
