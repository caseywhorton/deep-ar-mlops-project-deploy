# parameters for runtime

WEATHER_FEATURES = ['temperature_value', 'relativehumidity_value']
ELECTRICITY_FEATURES = ['value_demand']
S3_SERVING_PREFIX_URI = "s3://cw-weather-data-deployment/serving/"
S3_SERVING_INPUT_URI = "s3://cw-weather-data-deployment/serving/serving.json"
S3_FORECAST_PREFIX_URI = "s3://cw-weather-data-deployment/forecasts/"
