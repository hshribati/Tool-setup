# Weather Advisor Final Project
## Weather API Source Map and Data Report

**Course:** ITMO 544 - Cloud Computing

### 1. Weather Data Sources

The application uses three public APIs to get weather information.

**Zippopotam.us**
- Endpoint: https://api.zippopotam.us/us/{zip}
- Purpose: Convert a US ZIP code into a city, state, latitude, and longitude.
- Fields: places[0].latitude, places[0].longitude, places[0]["place name"], places[0].state.
- Example ZIP code: 60616.

**National Weather Service (NWS)**
- Endpoint: https://api.weather.gov/points/{latitude},{longitude}
- Purpose: Find forecast URLs and the local time zone.
- Fields: properties.forecastHourly, properties.forecastGridData, properties.timeZone.

The application then requests the hourly forecast URL returned by NWS.

- Hourly fields: properties.periods[].temperature, windSpeed, relativeHumidity.value, probabilityOfPrecipitation.value, shortForecast, startTime.
- Grid field: properties.visibility.values, when available.
- NWS visibility units: meters, converted to miles.

**Open-Meteo**

- Endpoint: https://api.open-meteo.com/v1/forecast
- Purpose: Provide UV Index and backup visibility forecasts.
- Fields: hourly.time, hourly.visibility, hourly.uv_index.
- Visibility is provided in meters and converted to miles.
- UV Index is a forecast value, not an AI-generated measurement.

The application does not use Gemini to generate weather measurements.

### 2. Weather Report Source Map

| Report Item | Source | Type | Missing Data |
|---|---|---|---|
| 1. Temperature | NWS hourly temperature | API fact, averaged | Not available |
| 2. Wind speed | NWS hourly windSpeed | API fact, parsed and averaged | Not available |
| 3. Visibility | NWS grid visibility; Open-Meteo backup | Forecast value, converted to miles | Not available |
| 4. UV Index | Open-Meteo hourly uv_index | Forecast value, averaged | Not available |
| 5. Humidity | NWS relativeHumidity.value | API fact, averaged | Not available |
| 6. Rain | NWS shortForecast and precipitation probability | Derived category | Unknown if probability is missing and rain is mentioned |
| 7. Snow | NWS shortForecast and precipitation probability | Derived category | Unknown if probability is missing and snow is mentioned |
| 8. Road conditions | Google Gemini or fallback rules | Advice | Fallback advice |
| 9. Clothing | Google Gemini or fallback rules | Advice | Fallback advice |
| 10. Accessories | Google Gemini or fallback rules | Advice | Fallback advice |

### 3. Forecast Time Periods

The application supports today and the next six days.

It uses the location's time zone from NWS.

**Morning:** 6:00 AM through 11:59 AM.

**Night:** 6:00 PM through 11:59 PM.

Hourly forecast records are selected using their local date and hour.

The application calculates average temperature, wind, and humidity for each period.

It uses the maximum precipitation probability for each period.

If a period has no hourly forecast records, the application marks that period as unavailable.

### 4. Rain and Snow Categories

The application checks the NWS shortForecast text for rain or snow.

If rain or snow is mentioned, it uses precipitation probability to assign a category.

| Probability | Category |
|---|---|
| 70% or higher | Heavy |
| 30% to less than 70% | Mild |
| Below 30% | No |
| Missing probability | Unknown |

These labels describe application-defined probability levels, not actual precipitation intensity. The same thresholds are used for both rain and snow. If the forecast does not mention rain or snow, the application returns No. If precipitation is mentioned but probability is missing, it returns Unknown.


### 5. Visibility

The application first checks NWS grid visibility values.

If NWS visibility is unavailable, it uses Open-Meteo hourly visibility forecasts.

Visibility values are converted from meters to miles:

Visibility in miles = Visibility in meters / 1609.344

The application calculates visibility for the selected morning or night period.

If neither source provides valid visibility data, the API returns null.

The webpage and email report display "Not available" for missing values.

### 6. UV Index

The application gets hourly UV Index forecasts from Open-Meteo.

It calculates the average UV Index for the selected morning or night period.

A nighttime UV Index of 0 is a valid value.

If UV data is unavailable, the API returns null.

The webpage and email report display "Not available" for missing values.

Open-Meteo values are weather forecasts, not direct measurements.

### 7. Google Gemini Advice

The Advisor application sends weather facts to Google Gemini.

Gemini generates three advice fields:

1. Clothing advice.
2. Accessories advice.
3. Road conditions advice.

The prompt tells Gemini not to invent missing weather information.

The application checks that Gemini returns valid JSON with three nonempty advice strings.

If Gemini fails, the application uses rule-based fallback advice.

Advice is not a direct weather measurement.

### 8. DynamoDB Cache

The Weather application uses DynamoDB to reduce repeated API calls.

**Table:** final-weather-cache

**Cache key:** weather#{zip}

**Cache duration:** 600 seconds (10 minutes).

The application stores weather forecasts, location details, source information, and an expiration timestamp.

If the cache has expired, the application requests new weather data.

If DynamoDB cannot be read, the application attempts to retrieve live weather data.

### 9. API Errors and Missing Information

The application handles these situations:

| Situation | Application Behavior |
|---|---|
| ZIP is not five digits | Returns HTTP 400 |
| ZIP cannot be found | Returns HTTP 404 |
| Date is invalid | Returns HTTP 400 |
| Date is outside seven-day range | Returns HTTP 400 |
| Weather API fails | Returns HTTP 502 after unsuccessful attempts |
| DynamoDB read fails | Attempts live weather retrieval |
| Visibility is missing | Returns null |
| UV Index is missing from Open-Meteo | Returns null |
| Gemini fails | Uses fallback advice |
| Forecast period is missing | Marks period unavailable |

### 10. Example API Request

Example ZIP code: 60616

Weather API request format:

GET /weather/60616?date=YYYY-MM-DD

The date must be today or within the next six days for the requested location.

Advisor API request format:

GET /advice?zip=60616&date=YYYY-MM-DD&gender=prefer-not-to-say

The Advisor API adds clothing, accessories, and road advice to the weather report.

### 11. Source Limitations

The National Weather Service may not provide all fields for every location or forecast time.

Visibility can be missing.

UV Index is supported through Open-Meteo, but may be unavailable if the API does not return valid data.

Hourly forecasts may not cover every hour of the seven-day request window.

The application does not use fake values to replace missing measurements.

A future version could add another reliable weather source and document its accuracy, coverage, and cost.

### 12. References

Zippopotam.us API:
https://api.zippopotam.us

National Weather Service API:
https://www.weather.gov/documentation/services-web-api

Google Gemini API:
https://ai.google.dev/gemini-api/docs

Amazon DynamoDB:
https://docs.aws.amazon.com/amazondynamodb/

AWS Systems Manager Parameter Store:
https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html

Amazon SNS:
https://docs.aws.amazon.com/sns/
