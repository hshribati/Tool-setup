const express = require('express');
const crypto = require('node:crypto');
const { SSMClient, GetParameterCommand } = require('@aws-sdk/client-ssm');
const {
  SNSClient,
  CreateTopicCommand,
  SubscribeCommand,
  PublishCommand,
  ListSubscriptionsByTopicCommand,
  SetTopicAttributesCommand
} = require('@aws-sdk/client-sns');

const app = express();

const PORT = Number(process.env.PORT || 3000);
const WEATHER_URL = process.env.WEATHER_URL || 'http://localhost:3000';
const AWS_REGION = process.env.AWS_REGION || 'us-east-2';
const GEMINI_API_BASE = process.env.GEMINI_API_BASE ||
  'https://generativelanguage.googleapis.com';
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-3.1-flash-lite';
const KEY_PARAM = process.env.GEMINI_KEY_PARAM ||
  '/itmo-444-544/gemini-api-key';

const ssm = new SSMClient({ region: AWS_REGION });
const sns = new SNSClient({ region: AWS_REGION });

const genders = ['woman', 'man', 'nonbinary', 'prefer-not-to-say'];
const subscriptionAttempts = new Map();

let cachedKey = null;
let keyTime = 0;

app.use(express.urlencoded({ extended: false, limit: '8kb' }));
app.use(express.json({ limit: '8kb' }));

function log(event, fields = {}) {
  console.log(JSON.stringify({
    time: new Date().toISOString(),
    event,
    ...fields
  }));
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[c]));
}

function validEmail(email) {
  return typeof email === 'string' &&
    email.length <= 254 &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function validGender(gender) {
  return genders.includes(gender);
}

async function getApiKey() {
  if (process.env.GEMINI_API_KEY) {
    return process.env.GEMINI_API_KEY;
  }

  if (cachedKey && Date.now() - keyTime < 300000) {
    return cachedKey;
  }

  const result = await ssm.send(new GetParameterCommand({
    Name: KEY_PARAM,
    WithDecryption: true
  }));

  if (!result.Parameter?.Value) {
    throw new Error('Gemini API key unavailable');
  }

  cachedKey = result.Parameter.Value;
  keyTime = Date.now();
  return cachedKey;
}

function fallback(period, gender) {
  if (!period?.available) {
    return {
      clothing: 'Weather information is not available for this period.',
      accessories: 'Check the forecast again later.',
      road: 'Check local road conditions before traveling.'
    };
  }

  const temp = Number(period.temperature);
  let clothing;

  if (temp <= 32) {
    clothing = 'Wear a heavy winter coat, warm pants, and boots.';
  } else if (temp <= 50) {
    clothing = 'Wear a warm jacket, long pants, and closed shoes.';
  } else if (temp <= 68) {
    clothing = 'Wear a light jacket or sweater.';
  } else if (temp <= 80) {
    clothing = 'Wear comfortable, light clothing.';
  } else {
    clothing = 'Wear light, breathable clothing.';
  }

  if (gender === 'woman' || gender === 'man') {
    clothing += ' Choose comfortable layers that fit your style.';
  }

  const rain = period.rain && period.rain !== 'No';
  const snow = period.snow && period.snow !== 'No';

  const accessories = rain || snow
    ? 'Bring waterproof clothing and suitable shoes.'
    : temp <= 32
      ? 'Bring gloves, a scarf, and a warm hat.'
      : 'Bring comfortable shoes and water.';

  const road = snow
    ? 'Snow may make roads slippery. Drive carefully.'
    : rain
      ? 'Wet roads may be slippery. Slow down.'
      : 'No rain or snow is reported. Check local road conditions.';

  return { clothing, accessories, road };
}

async function geminiAdvice(period, gender) {
  const key = await getApiKey();

  const prompt = `
Give short, practical weather advice using ONLY the supplied facts.

Do not invent visibility, UV, road conditions, or weather events.
Road advice must be cautious, not a guarantee of road safety.
Do not assume clothing preferences based on gender.

Gender selection: ${gender}
Weather facts: ${JSON.stringify(period)}

Return ONLY valid JSON:
{
  "clothing": "short clothing advice",
  "accessories": "short accessories advice",
  "road": "short road advice"
}
`;

  const url =
    `${GEMINI_API_BASE}/v1beta/models/${GEMINI_MODEL}:generateContent`;

  const requestBody = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      responseMimeType: 'application/json',
      maxOutputTokens: 400
    }
  };

  const retryableStatuses = [429, 500, 502, 503, 504];

  for (let attempt = 1; attempt <= 3; attempt++) {
    let response;

    try {
      response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-goog-api-key': key
        },
        body: JSON.stringify(requestBody),
        signal: AbortSignal.timeout(45000)
      });
    } catch (error) {
      if (attempt === 3) {
        throw new Error(
          `Gemini request failed after 3 attempts: ${error.message}`
        );
      }

      await new Promise(resolve =>
        setTimeout(resolve, 1500 * (2 ** (attempt - 1)))
      );
      continue;
    }

    if (!response.ok) {
      const errorBody = await response.text();
      let detail = errorBody;

      try {
        const parsed = JSON.parse(errorBody);
        detail = parsed.error?.message || errorBody;
      } catch {
        // Keep original response.
      }

      if (
        retryableStatuses.includes(response.status) &&
        attempt < 3
      ) {
        const retryAfter = Number(
          response.headers.get('retry-after')
        );

        const delay =
          Number.isFinite(retryAfter) && retryAfter > 0
            ? Math.min(retryAfter * 1000, 10000)
            : 1500 * (2 ** (attempt - 1));

        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }

      throw new Error(
        `Gemini HTTP ${response.status}: ${detail.slice(0, 500)}`
      );
    }

    const data = await response.json();

    const raw = data.candidates?.[0]?.content?.parts
      ?.map(part => part.text || '')
      .join('');

    if (!raw) {
      throw new Error('Empty Gemini response');
    }

    const result = JSON.parse(raw);

    for (const field of ['clothing', 'accessories', 'road']) {
      if (
        typeof result[field] !== 'string' ||
        !result[field].trim() ||
        result[field].length > 500
      ) {
        throw new Error('Invalid Gemini response');
      }
    }

    return {
      clothing: result.clothing,
      accessories: result.accessories,
      road: result.road
    };
  }

  throw new Error('Gemini request failed after 3 attempts');
}
async function advisePeriod(period, gender) {
  if (!period?.available) {
    return {
      ...fallback(period, gender),
      source: 'fallback'
    };
  }

  try {
    return {
      ...(await geminiAdvice(period, gender)),
      source: 'gemini'
    };
  } catch (error) {
    log('gemini_fallback', { message: error.message });

    return {
      ...fallback(period, gender),
      source: 'fallback'
    };
  }
}

async function getAdvice(zip, date, gender) {
  if (!/^\d{5}$/.test(zip)) {
    return {
      status: 400,
      body: { error: 'Enter a valid 5-digit ZIP code.' }
    };
  }

  if (!validGender(gender)) {
    return {
      status: 400,
      body: { error: 'Select a valid gender option.' }
    };
  }

  if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return {
      status: 400,
      body: { error: 'Enter a valid date.' }
    };
  }

  try {
    const url = new URL(`/weather/${zip}`, WEATHER_URL);

    if (date) {
      url.searchParams.set('date', date);
    }

    const response = await fetch(url, {
      signal: AbortSignal.timeout(20000)
    });

    const weather = await response.json();

    if (!response.ok) {
      return {
        status: response.status,
        body: weather
      };
    }

    const [morningAdvice, nightAdvice] = await Promise.all([
      advisePeriod(weather.morning, gender),
      advisePeriod(weather.night, gender)
    ]);

    return {
      status: 200,
      body: {
        ...weather,
        gender,
        morning: {
          ...weather.morning,
          clothingAdvice: morningAdvice.clothing,
          accessoriesAdvice: morningAdvice.accessories,
          roadConditions: morningAdvice.road,
          adviceSource: morningAdvice.source
        },
        night: {
          ...weather.night,
          clothingAdvice: nightAdvice.clothing,
          accessoriesAdvice: nightAdvice.accessories,
          roadConditions: nightAdvice.road,
          adviceSource: nightAdvice.source
        }
      }
    };
  } catch (error) {
    log('advisor_error', { message: error.message });

    return {
      status: 502,
      body: { error: 'Weather service is unavailable.' }
    };
  }
}

function privateTopicName(email) {
  const normalized = email.trim().toLowerCase();

  const hash = crypto
    .createHash('sha256')
    .update(normalized)
    .digest('hex');

  return `final-weather-recipient-${hash}`;
}

async function securePrivateTopic(topicArn) {
  const accountId = topicArn.split(':')[4];
  const advisorRoleArn =
    `arn:aws:iam::${accountId}:role/itmo-444-544-advisor-role`;

  const policy = {
    Version: '2012-10-17',
    Statement: [
      {
        Sid: 'DenyUnauthorizedSubscriptions',
        Effect: 'Deny',
        Principal: '*',
        Action: [
          'sns:Subscribe',
          'sns:SetTopicAttributes',
          'sns:AddPermission',
          'sns:RemovePermission'
        ],
        Resource: topicArn,
        Condition: {
          ArnNotEquals: {
            'aws:PrincipalArn': advisorRoleArn
          }
        }
      }
    ]
  };

  await sns.send(new SetTopicAttributesCommand({
    TopicArn: topicArn,
    AttributeName: 'Policy',
    AttributeValue: JSON.stringify(policy)
  }));
}

function formatWeatherEmail(report) {
  const formatPeriod = (title, period = {}) => {
    const value = (field) => {
      const item = period[field];
      return item === undefined || item === null || item === ''
        ? 'Not available'
        : String(item);
    };

    const withUnit = (field, unit) => {
      const result = value(field);
      return result === 'Not available'
        ? result
        : result + unit;
    };

    return [
      title,
      `Temperature: ${withUnit('temperature', '°F')}`,
      `Wind: ${withUnit('windSpeedMph', ' mph')}`,
      `Visibility: ${withUnit('visibility', ' miles')}`,
      `UV Index: ${value('uvIndex')}`,
      `Humidity: ${withUnit('humidity', '%')}`,
      `Rain: ${value('rain')}`,
      `Snow: ${value('snow')}`,
      `Road conditions: ${value('roadConditions')}`,
      `Clothing: ${value('clothingAdvice')}`,
      `Accessories: ${value('accessoriesAdvice')}`
    ].join('\\n');
  };

  return [
    'Your Weather Advisor Report',
    `ZIP Code: ${report.zip || 'Not available'}`,
    `Date: ${report.date || 'Not available'}`,
    '',
    formatPeriod('MORNING', report.morning),
    '',
    formatPeriod('NIGHT', report.night)
  ].join('\\n');
}

async function getTopicSubscriptions(topicArn) {
  const subscriptions = [];
  let nextToken;

  do {
    const response = await sns.send(
      new ListSubscriptionsByTopicCommand({
        TopicArn: topicArn,
        ...(nextToken ? { NextToken: nextToken } : {})
      })
    );

    subscriptions.push(...(response.Subscriptions || []));
    nextToken = response.NextToken;
  } while (nextToken);

  return subscriptions;
}

async function subscribeEmail(email) {
  const normalized = email.trim().toLowerCase();

  const topic = await sns.send(new CreateTopicCommand({
    Name: privateTopicName(normalized)
  }));

  if (!topic.TopicArn) {
    throw new Error('Could not create private SNS topic');
  }

  await securePrivateTopic(topic.TopicArn);
  const subscriptions = await getTopicSubscriptions(topic.TopicArn);

  const unexpected = subscriptions.some(item =>
    item.Protocol !== 'email' ||
    item.Endpoint?.toLowerCase() !== normalized
  );

  if (unexpected) {
    throw new Error('Private topic contains an unexpected subscription');
  }

  const existing = subscriptions.find(item =>
    item.Protocol === 'email' &&
    item.Endpoint?.toLowerCase() === normalized
  );

  if (!existing) {
    await sns.send(new SubscribeCommand({
      TopicArn: topic.TopicArn,
      Protocol: 'email',
      Endpoint: normalized,
      ReturnSubscriptionArn: true
    }));
  }

  return {
    topicArn: topic.TopicArn,
    confirmed: Boolean(
      existing &&
      existing.SubscriptionArn &&
      existing.SubscriptionArn !== 'PendingConfirmation'
    )
  };
}

async function sendWeatherEmail(email, report) {
  const normalized = email.trim().toLowerCase();

  if (!validEmail(normalized)) {
    throw new Error('Invalid recipient email');
  }

  const subscription = await subscribeEmail(normalized);

  if (!subscription.confirmed) {
    return {
      status: 'pending_confirmation',
      message: 'Confirm your email subscription before receiving reports.'
    };
  }

  const subscriptions = await getTopicSubscriptions(
    subscription.topicArn
  );

  const authorized = subscriptions.length === 1 &&
    subscriptions[0].Protocol === 'email' &&
    subscriptions[0].Endpoint?.toLowerCase() === normalized &&
    subscriptions[0].SubscriptionArn &&
    subscriptions[0].SubscriptionArn !== 'PendingConfirmation';

  if (!authorized) {
    throw new Error('Recipient verification failed');
  }

  const message = formatWeatherEmail(report);

  await sns.send(new PublishCommand({
    TopicArn: subscription.topicArn,
    Subject: 'Your Weather Advisor Report',
    Message: message
  }));

  return {
    status: 'sent',
    message: 'Weather report submitted to SNS for email delivery.'
  };
}

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'advisor' });
});

app.get('/advice', async (req, res) => {
  const result = await getAdvice(
    String(req.query.zip || ''),
    String(req.query.date || ''),
    String(req.query.gender || 'prefer-not-to-say')
  );

  res.status(result.status).json(result.body);
});

app.post('/subscribe', async (req, res) => {
  const email = String(req.body.email || '').trim();
  const consent = req.body.emailConsent === 'yes';

  const zip = String(req.body.zip || '').trim();
  const date = String(req.body.date || '').trim();
  const gender = String(req.body.gender || '').trim();

  if (!/^\d{5}$/.test(zip)) {
    return res.status(400).json({
      error: 'Enter a valid 5-digit ZIP code.'
    });
  }

  if (!validGender(gender)) {
    return res.status(400).json({
      error: 'Select a valid gender option.'
    });
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) ||
      !Number.isFinite(Date.parse(date + 'T00:00:00Z'))) {
    return res.status(400).json({
      error: 'Enter a valid date.'
    });
  }

  const selectedDate = Date.parse(date + 'T00:00:00Z');
  const today = new Date();
  const todayUTC = Date.UTC(
    today.getUTCFullYear(),
    today.getUTCMonth(),
    today.getUTCDate()
  );

  if (
    !Number.isFinite(selectedDate) ||
    selectedDate < todayUTC ||
    selectedDate >= todayUTC + 7 * 86400000
  ) {
    return res.status(400).json({
      error: 'Select a date from today through the next 6 days.'
    });
  }

  if (!consent) {
    return res.status(400).json({
      error: 'Email consent is required.'
    });
  }

  if (!validEmail(email)) {
    return res.status(400).json({
      error: 'Enter a valid email address.'
    });
  }

  const key = email.toLowerCase();
  const now = Date.now();
  const lastAttempt = subscriptionAttempts.get(key);

  if (lastAttempt && now - lastAttempt < 600000) {
    return res.status(429).json({
      error: 'Please wait before requesting another email.'
    });
  }

  if (subscriptionAttempts.size > 1000) {
    subscriptionAttempts.clear();
  }

  subscriptionAttempts.set(key, now);

  try {
    const subscription = await subscribeEmail(email);

    if (!subscription.confirmed) {
      return res.json({
        status: 'pending_confirmation',
        message: 'Check your email and confirm your SNS subscription.'
      });
    }

    const result = await getAdvice(zip, date, gender);

    if (result.status !== 200) {
      return res.status(result.status).json(result.body);
    }

    const delivery = await sendWeatherEmail(
      email,
      result.body
    );

    return res.json(delivery);
  } catch (error) {
    subscriptionAttempts.delete(key);
    log('sns_subscription_failed', { message: error.message });

    return res.status(502).json({
      error: 'Email subscription is unavailable.'
    });
  }
});

function renderPeriod(period, type) {
  const icon = type === 'morning' ? '☀️' : '🌙';

  if (!period?.available) {
    return `
      <section class="forecast">
        <h3>${icon} ${escapeHtml(period?.label || 'Forecast')}</h3>
        <p>Weather information is not available.</p>
      </section>
    `;
  }

  return `
    <section class="forecast ${type}">
      <div class="forecast-header">
        <h3>${icon} ${escapeHtml(period.label)}</h3>
        <span class="temperature">${escapeHtml(period.temperature)}°F</span>
      </div>

      <p class="conditions">${escapeHtml(period.shortForecast)}</p>

      <div class="weather-grid">
        <div class="weather-item">
          <span>💨 Wind</span>
          <strong>${escapeHtml(period.windSpeedMph)} mph</strong>
        </div>
        <div class="weather-item">
          <span>💧 Humidity</span>
          <strong>${escapeHtml(period.humidity)}%</strong>
        </div>
        <div class="weather-item">
          <span>👁️ Visibility</span>
          <strong>${period.visibility == null ? 'Not available' : escapeHtml(period.visibility) + ' miles'}</strong>
        </div>
        <div class="weather-item">
          <span>☀️ UV Index</span>
          <strong>${period.uvIndex == null ? 'Not available' : escapeHtml(period.uvIndex)}</strong>
        </div>
        <div class="weather-item">
          <span>🌧️ Rain</span>
          <strong>${escapeHtml(period.rain)}</strong>
        </div>
        <div class="weather-item">
          <span>❄️ Snow</span>
          <strong>${escapeHtml(period.snow)}</strong>
        </div>
      </div>

      <div class="advice">
        <h4>✨ AI Weather Advice</h4>
        <p><strong>👕 Clothing:</strong>
          ${escapeHtml(period.clothingAdvice)}</p>
        <p><strong>🎒 Accessories:</strong>
          ${escapeHtml(period.accessoriesAdvice)}</p>
        <p><strong>🚗 Road:</strong>
          ${escapeHtml(period.roadConditions)}</p>
        <p class="small">Advice source:
          ${escapeHtml(period.adviceSource)}</p>
      </div>
    </section>
  `;
}

app.get('/', async (req, res) => {
  const zip = String(req.query.zip || '');
  const date = String(req.query.date || '');
  const gender = String(req.query.gender || 'prefer-not-to-say');

  let result = '';

  if (zip) {
    const response = await getAdvice(zip, date, gender);

    if (response.status === 200) {
      const body = response.body;

      result = `
        <div class="results">
          <div class="location-header">
            <h2>📍 ${escapeHtml(body.city)},
              ${escapeHtml(body.state)}</h2>
            <p>Forecast for ${escapeHtml(body.date)}</p>
          </div>

          <div class="forecast-grid">
            ${renderPeriod(body.morning, 'morning')}
            ${renderPeriod(body.night, 'night')}
          </div>
        </div>
      `;
    } else {
      result = `
        <div class="error">
          ${escapeHtml(response.body.error || 'Request failed.')}
        </div>
      `;
    }
  }

  res.set('Content-Type', 'text/html; charset=utf-8');

  res.send(`
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Weather Advisor</title>
  <style>
    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      padding: 40px 20px;
      font-family: Arial, sans-serif;
      color: #17365d;
      background: linear-gradient(135deg, #0754a6, #1594d5, #75d4f4);
      background-attachment: fixed;
    }

    .container {
      max-width: 1050px;
      margin: 0 auto;
    }

    .hero {
      text-align: center;
      color: white;
      padding: 30px 0;
    }

    .hero h1 {
      font-size: 46px;
      margin: 0 0 12px;
      color: white;
    }

    .hero p {
      font-size: 18px;
      color: #eaf6ff;
    }

    .card, .forecast {
      background: white;
      border-radius: 22px;
      padding: 28px;
      margin: 22px 0;
      box-shadow: 0 12px 35px rgba(0, 40, 100, 0.18);
    }

    h2 {
      color: #14529a;
    }

    .field {
      margin-bottom: 20px;
    }

    .field label {
      display: block;
      font-weight: bold;
      margin-bottom: 8px;
    }

    .field input, .field select {
      width: 100%;
      padding: 14px;
      border: 1px solid #b8d4ee;
      border-radius: 10px;
      font-size: 16px;
      background: #f8fbff;
    }

    .field input:focus, .field select:focus {
      outline: 2px solid #3b9bff;
    }

    button {
      width: 100%;
      padding: 15px;
      background: linear-gradient(90deg, #1263c5, #22a7ed);
      color: white;
      border: none;
      border-radius: 12px;
      font-size: 17px;
      font-weight: bold;
      cursor: pointer;
    }

    button:hover {
      filter: brightness(1.08);
    }

    .location-header {
      text-align: center;
      color: white;
      margin-top: 35px;
    }

    .location-header h2 {
      color: white;
      font-size: 30px;
      margin-bottom: 5px;
    }

    .location-header p {
      color: #eaf6ff;
    }

    .forecast-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
    }

    .forecast {
      margin: 12px 0;
      border-top: 6px solid #2496e8;
    }

    .forecast.night {
      border-top-color: #6258c7;
    }

    .forecast-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    .forecast-header h3 {
      font-size: 24px;
      margin: 0;
    }

    .temperature {
      font-size: 28px;
      font-weight: bold;
      color: #1263c5;
    }

    .conditions {
      color: #63758b;
      font-size: 17px;
    }

    .weather-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin: 20px 0;
    }

    .weather-item {
      padding: 15px;
      border-radius: 12px;
      background: #edf7ff;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .weather-item span {
      font-size: 14px;
      color: #5b7390;
    }

    .weather-item strong {
      font-size: 18px;
      color: #174b83;
    }

    .advice {
      padding: 20px;
      margin-top: 18px;
      border-radius: 14px;
      background: #eaf5ff;
      line-height: 1.6;
    }

    .advice h4 {
      margin-top: 0;
      color: #14529a;
      font-size: 18px;
    }

    .consent {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin: 20px 0;
      line-height: 1.5;
    }

    .consent input {
      margin-top: 4px;
    }

    .small {
      color: #63758b;
      font-size: 13px;
    }

    .error {
      background: white;
      padding: 20px;
      border-radius: 12px;
      color: #b42318;
      font-weight: bold;
    }

    .footer {
      text-align: center;
      color: #eaf6ff;
      margin: 30px 0;
      font-size: 13px;
    }

    @media (max-width: 750px) {
      .forecast-grid {
        grid-template-columns: 1fr;
      }

      .hero h1 {
        font-size: 34px;
      }

      .card, .forecast {
        padding: 20px;
      }
    }
  </style>
</head>
<body>
  <main class="container">
    <header class="hero">
      <h1>☀️ Weather Advisor</h1>
      <p>Your smart weather assistant powered by AI</p>
    </header>

    <section class="card">
      <h2>🌤️ Check Your Weather</h2>
      <p>Enter your ZIP code to get personalized morning and night advice.</p>

      <form method="GET" action="/">
        <div class="field">
          <label for="zip">📍 US ZIP Code</label>
          <input id="zip" name="zip"
            pattern="[0-9]{5}" maxlength="5"
            placeholder="Example: 60616"
            value="${escapeHtml(zip)}" required>
        </div>

        <div class="field">
          <label for="date">📅 Forecast Date</label>
          <input id="date" type="date" name="date"
            value="${escapeHtml(date)}">
        </div>

        <div class="field">
          <label for="gender">👤 Gender</label>
          <select id="gender" name="gender">
            ${genders.map(g => `
              <option value="${g}"
                ${gender === g ? 'selected' : ''}>
                ${escapeHtml(g)}
              </option>
            `).join('')}
          </select>
        </div>

        <button type="submit">🌤️ Get Weather Advice</button>
      </form>
    </section>

    ${result}

    <section class="card">
      <h2>✉️ Email Subscription</h2>
      <p>Request an email subscription confirmation through AWS SNS.</p>

      <form method="POST" action="/subscribe">
        <div class="field">
          <label for="email-zip">📍 ZIP Code</label>
          <input id="email-zip" name="zip"
            pattern="[0-9]{5}" maxlength="5"
            placeholder="Example: 60016"
            value="${escapeHtml(zip)}" required>
        </div>
        <div class="field">
          <label for="email-date">📅 Forecast Date</label>
          <input id="email-date" type="date" name="date"
            value="${escapeHtml(date)}" required>
        </div>
        <input type="hidden" name="gender"
          value="${escapeHtml(gender)}">
        <div class="field">
          <label for="email">Email Address</label>
          <input id="email" type="email" name="email"
            placeholder="you@example.com"
            maxlength="254" required>
        </div>

        <label class="consent">
          <input type="checkbox" name="emailConsent"
            value="yes" required>
          <span>I agree to receive email notifications
            and understand that I must confirm my subscription.</span>
        </label>

        <button type="submit">✉️ Request Email Confirmation</button>
      </form>

      <p class="small">Email is optional. Personalized weather
        reports are not sent automatically yet.</p>
    </section>

    <footer class="footer">
      Weather data: National Weather Service | AI: Google Gemini
    </footer>
  </main>
</body>
</html>
  `);
});

app.listen(PORT, () => {
  log('advisor_started', {
    port: PORT,
    model: GEMINI_MODEL
  });
});
