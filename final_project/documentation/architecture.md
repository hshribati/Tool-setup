# Final Project: Weather Advisor Application
## 1. Architecture Document

**Course:** ITMO 544 - Cloud Computing
**Project:** Weather Advisor Application
**AWS Region:** us-east-2

### 1.1 Project Overview

The Weather Advisor application helps users plan their day based on weather conditions.

Users enter a US ZIP code, forecast date, and gender option. The application displays morning and night weather reports with clothing, accessories, and road advice.

Users can also request a weather report by email. Email delivery uses AWS SNS and requires the recipient to confirm their subscription.

The project uses AWS infrastructure, the National Weather Service, and Google Gemini.

### 1.2 Architecture Diagram

```text
                     USER / WEB BROWSER
                             |
                             v
                 AWS APPLICATION LOAD BALANCER
                       /             \
                      /               \
               PORT 8081           PORT 8080
                   |                   |
                   v                   v
              ADVISOR APP         WEATHER APP
              Node.js / EC2       Node.js / EC2
              Auto Scaling        Auto Scaling
                   |                   |
                   |                   +----> Zippopotam.us
                   |                   |      ZIP to coordinates
                   |                   |
                   |                   +----> National Weather
                   |                   |      Service API
                   |                   |
                   |                   +----> DynamoDB
                   |                          Weather cache
                   |
                   +----> AWS Systems Manager
                   |      Gemini API key
                   |
                   +----> Google Gemini API
                   |      Weather advice
                   |
                   +----> AWS SNS
                          Email confirmation
                          and weather reports
```

The Advisor application also calls the Weather application through the load balancer on port 8080.

Both applications listen on port 3000 inside their EC2 instances.

### 1.3 AWS Components

| Component | Purpose |
|---|---|
| Amazon EC2 | Runs the Weather and Advisor applications |
| Application Load Balancer | Sends requests to the correct application |
| Auto Scaling Groups | Manage EC2 instances for both applications |
| Launch Templates | Define how EC2 instances start |
| Security Groups | Control network access |
| IAM Roles | Give applications access to required AWS services |
| DynamoDB | Stores cached weather information |
| Systems Manager Parameter Store | Stores the Gemini API key |
| Amazon SNS | Sends email confirmation and weather reports |
| VPC and Subnets | Provide the AWS network |

### 1.4 Request Flow 1: Weather Report

1. The user opens the Advisor website on port 8081.
2. The user enters a ZIP code, date, and gender option.
3. The Advisor application checks the input.
4. The Advisor application requests weather data through port 8080.
5. The Weather application checks DynamoDB for cached information.
6. If the cache is empty or expired, it looks up the ZIP code using Zippopotam.us.
7. The Weather application requests forecast information from the National Weather Service.
8. The application saves the weather data in DynamoDB for 600 seconds.
9. The Weather application creates morning and night summaries.
10. The Advisor application requests advice from Google Gemini.
11. If Gemini fails, the application uses basic rule-based advice.
12. The Advisor application returns the weather report to the user.

### 1.5 Request Flow 2: Email Report

1. The user enters an email address and weather report details.
2. The user agrees to receive email notifications.
3. The Advisor application checks the information and consent.
4. The application creates or finds a private SNS topic for the recipient.
5. SNS sends a subscription confirmation email if needed.
6. The user confirms the subscription.
7. On a later valid request, the application verifies the confirmed recipient.
8. The application generates the weather report.
9. SNS publishes the report to the recipient's private topic.
10. The application reports whether the email was submitted or confirmation is still needed.

### 1.6 Weather Information and Advice

The project separates information into three types.

**Facts from APIs:**
- Temperature
- Wind speed
- Humidity
- Probability of precipitation
- Forecast description
- Visibility when available
- Location and time zone

**Values calculated by the application:**
- Morning and night summaries
- Average temperature
- Average wind speed
- Average humidity
- Maximum precipitation probability
- Rain and snow categories
- Conversion of visibility from meters to miles

**Advice:**
- Clothing suggestions
- Accessories suggestions
- Road safety advice

Advice comes from Google Gemini when available. If Gemini fails or a period has no forecast, the application uses rule-based fallback advice.

The application does not treat AI advice as measured weather data.

### 1.7 Forecast Rules

The user can request today or one of the next six days.

Morning covers 6:00 AM through 11:59 AM.

Night covers 6:00 PM through 11:59 PM.

The Weather application uses the time zone returned by the National Weather Service.

The application uses these precipitation probability categories:

| Probability | Category |
|---|---|
| 70% or higher | Heavy |
| 30% to less than 70% | Mild |
| Below 30% | No |
| Missing probability | Unknown |

These are application-defined labels based on precipitation probability. They are not official measurements of rain or snow intensity.

Rain and snow are also identified using words in the NWS forecast description.

The Weather application obtains UV Index from Open-Meteo. Open-Meteo also provides backup visibility forecasts. If either value is missing, the application returns an unavailable value rather than inventing information.

Visibility is requested from NWS grid data. When it is missing, the application returns a null value rather than inventing information.

### 1.8 Design Decision Table

| # | Decision | Alternatives Considered | Reason for Selection |
|---|---|---|---|
| 1 | Use Python for AWS infrastructure | Manual AWS setup | Supports automated creation and cleanup |
| 2 | Use Node.js and Express | Python web framework | Supports the existing application code and API endpoints |
| 3 | Separate Weather and Advisor services | One combined application | Keeps weather processing separate from advice |
| 4 | Use one ALB with two listener ports | Separate load balancers | Reduces infrastructure while routing requests to both services |
| 5 | Use EC2 Auto Scaling groups | Manually managed EC2 instances | Supports instance replacement and recovery |
| 6 | Use launch templates | Manual instance configuration | Provides consistent EC2 configuration |
| 7 | Use DynamoDB | PostgreSQL database | Stores weather data without managing a database server |
| 8 | Cache weather for 600 seconds | Request live weather every time | Reduces repeated external API requests |
| 9 | Use Zippopotam.us | Manually enter coordinates | Converts US ZIP codes into coordinates |
| 10 | Use National Weather Service | Use only a commercial weather API | Provides weather forecast information |
| 11 | Use local time zones | Use UTC for all reports | Makes morning and night match the selected location |
| 12 | Use Google Gemini | Generate all advice with fixed rules | Provides AI-generated practical weather advice |
| 13 | Use rule-based fallback advice | Return an error when Gemini fails | Keeps basic advice available |
| 14 | Use SSM Parameter Store | Store the Gemini key in source code | Keeps the API key outside the source code |
| 15 | Use separate IAM roles | Share one IAM role | Limits access for each application |
| 16 | Use SNS email confirmation | Send emails without confirmation | Requires recipients to confirm subscriptions |
| 17 | Use separate SNS topics per recipient | Share one topic | Helps isolate recipient subscriptions |
| 18 | Validate user input | Accept all submitted values | Rejects invalid requests |
| 19 | Escape HTML output | Display submitted values directly | Helps prevent HTML injection |
| 20 | Use retries for external APIs | Fail immediately after one attempt | Handles some temporary service failures |

### 1.9 Security and Threat Table

| Threat | Current Protection | Remaining Risk |
|---|---|---|
| Invalid ZIP code | Server checks for five digits | A five-digit ZIP may still not exist |
| Invalid date | Server validates date format and range | Advisor and Weather use different date boundaries |
| Invalid gender | Server checks allowed options | Gender is sent to Gemini for advice |
| HTML injection | HTML escaping | Other output paths still need testing |
| Exposed Gemini key | SSM Parameter Store with decryption | Key access depends on IAM permissions |
| Unauthorized AWS access | Separate IAM roles | IAM policies need least-privilege review |
| Unwanted email | Consent and SNS confirmation | Email requests may still be abused |
| Email sent to wrong recipient | Private SNS topics and recipient checks | Topic policy and isolation require testing |
| Too many email requests | Ten-minute in-memory limit per email | Limit is not shared across EC2 instances |
| Too many Gemini requests | API retries and fallback | No verified shared daily call cap |
| External weather outage | Retries and cached data | Expired cache is not used as a stale fallback |
| Gemini outage | Rule-based fallback | Advice may be less personalized |
| Missing weather fields | Missing values remain unavailable; visibility and UV display Not available when missing | Other report fields still need final display testing |
| EC2 instance failure | Auto Scaling groups | Actual recovery time must be measured |
| Unencrypted web traffic | No HTTPS configuration confirmed | HTTP may expose user input in transit |

### 1.10 Reliability and Error Handling

The Weather application retries some failed external API requests to handle temporary problems.

Weather information is stored in DynamoDB for 600 seconds to reduce repeated API requests.

The Advisor application uses rule-based fallback advice if Gemini is unavailable or returns invalid information.

Both applications provide health endpoints for service checks.

AWS Auto Scaling groups manage application instances and can replace unhealthy instances.

The project includes automated unit, integration, and chaos tests to check application and infrastructure behavior.

#### Performance and Recovery Targets

- Response-time SLO: 120 milliseconds.
- Load test: 10 concurrent users.
- Recovery target: 180 seconds.
- Recovery testing checks whether an application works after an EC2 instance is terminated and replaced.

The response-time and recovery targets must be verified through actual testing.

The final test evidence should include response times, failure rates, recovery times, and whether each target was achieved.

Integration and chaos test results must be added after the final AWS deployment and testing.

### 1.11 Privacy

The application asks for email consent before creating a subscription.

SNS requires the recipient to confirm the subscription.

The application uses a separate SNS topic for each recipient and checks the topic subscriptions before sending reports.

The application does not intentionally include the recipient's email address or gender in its normal application log messages.

ZIP codes and forecast dates are included in some weather logs.

Email addresses are not stored in the DynamoDB weather cache. SNS stores subscription information for email delivery.

### 1.12 Known Limitations and Future Improvements

The following items need improvement or further verification before production:

1. Verify visibility and UV Index display through the final integration tests.
3. Make date validation consistent across both applications.
4. Add HTTPS for browser and service traffic.
5. Add shared rate limits and a daily Gemini request cap.
6. Measure response times and EC2 recovery times.
7. Review IAM policies and SNS topic permissions.
8. Improve handling of weather API outages and expired cache data.
9. Check AWS billing for actual project costs.
10. Improve the email form text to match its real behavior.

### 1.13 Deployment and Cleanup

The Python project creates the AWS application infrastructure.

The main deployment script is `create.py`.

The main cleanup script is `delete.py`.

The deployment checks that the DynamoDB weather cache table already exists.

The application infrastructure includes IAM resources, networking, an ALB, launch templates, target groups, listeners, and Auto Scaling groups.

The cleanup process removes the application infrastructure in reverse order.

DynamoDB, SNS subscriptions/topics, and the Gemini SSM parameter may require separate cleanup.

### 1.14 Conclusion

The Weather Advisor application combines AWS infrastructure, weather APIs, and Google Gemini to provide morning and night weather advice.

The two-service design separates weather data from AI advice.

DynamoDB reduces repeated weather requests, Auto Scaling manages application instances, and SNS supports confirmed email delivery.

The project also includes input validation, IAM roles, fallback advice, and automated infrastructure tests.

Before production use, the main improvements would be HTTPS, shared abuse controls, stronger monitoring, and complete weather field coverage.
