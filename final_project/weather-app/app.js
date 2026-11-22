
'use strict';

const express = require('express');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const {
  DynamoDBDocumentClient,
  GetCommand,
  PutCommand
} = require('@aws-sdk/lib-dynamodb');

const app = express();

const PORT = Number(process.env.PORT || 3000);
const REGION = process.env.AWS_REGION || 'us-east-2';
const WEATHER_TABLE = process.env.WEATHER_TABLE || 'final-weather-cache';
const CACHE_SECONDS = Number(process.env.CACHE_SECONDS || 600);

const ZIP_API = process.env.ZIP_API_BASE || 'https://api.zippopotam.us';
const NWS_API = process.env.NWS_API_BASE || 'https://api.weather.gov';

const USER_AGENT =
  process.env.NWS_USER_AGENT ||
  '(ITMO 544 Final Weather Advisor, hshribati@hawk.illinoistech.edu)';

const dynamodb = DynamoDBDocumentClient.from(
  new DynamoDBClient({ region: REGION }),
  { marshallOptions: { removeUndefinedValues: true } }
);

function log(event, fields = {}) {
  console.log(JSON.stringify({
    time: new Date().toISOString(),
    event,
    ...fields
  }));
}

function validZip(zip) {
  return typeof zip === 'string' && /^\d{5}$/.test(zip);
}

function validDate(date) {
  return typeof date === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(date) &&
    !Number.isNaN(Date.parse(date + 'T00:00:00Z'));
}

function dateInRange(date, today) {
  if (!validDate(date)) return false;

  const selected = Date.parse(date + 'T00:00:00Z');
  const start = Date.parse(today + 'T00:00:00Z');

  return selected >= start &&
    selected < start + 7 * 24 * 60 * 60 * 1000;
}

function localDate(iso, timezone) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(new Date(iso));
}

function localHour(iso, timezone) {
  return Number(new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    hour: '2-digit',
    hourCycle: 'h23'
  }).format(new Date(iso)));
}

function todayInTimezone(timezone) {
  return localDate(new Date().toISOString(), timezone);
}

async function fetchJson(url, attempts = 3) {
  let lastError;

  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      const response = await fetch(url, {
        headers: {
          'User-Agent': USER_AGENT,
          'Accept': 'application/geo+json, application/json'
        },
        signal: AbortSignal.timeout(10000)
      });

      if (response.ok) return await response.json();

      const error = new Error(`HTTP ${response.status}`);
      error.status = response.status;

      if (response.status < 500 && response.status !== 429) {
        throw error;
      }

      lastError = error;
    } catch (error) {
      lastError = error;

      if (error.status && error.status < 500 && error.status !== 429) {
        throw error;
      }
    }

    if (attempt < attempts) {
      await new Promise(resolve =>
        setTimeout(resolve, attempt * 500)
      );
    }
  }

  throw lastError;
}

async function readCache(zip) {
  try {
    const response = await dynamodb.send(new GetCommand({
      TableName: WEATHER_TABLE,
      Key: { id: `weather#${zip}` }
    }));

    const item = response.Item;

    if (!item || item.expires_at <= Math.floor(Date.now() / 1000)) {
      return null;
    }

    return item.data;
  } catch (error) {
    log('cache_read_failed', { message: error.message });
    return null;
  }
}

async function saveCache(zip, data) {
  try {
    const now = Math.floor(Date.now() / 1000);

    await dynamodb.send(new PutCommand({
      TableName: WEATHER_TABLE,
      Item: {
        id: `weather#${zip}`,
        data,
        updated_at: new Date().toISOString(),
        expires_at: now + CACHE_SECONDS
      }
    }));
  } catch (error) {
    log('cache_write_failed', { message: error.message });
  }
}

function average(values) {
  const valid = values.filter(value =>
    typeof value === 'number' && Number.isFinite(value)
  );

  if (!valid.length) return null;

  return Math.round(
    (valid.reduce((sum, value) => sum + value, 0) /
      valid.length) * 10
  ) / 10;
}

function maximum(values) {
  const valid = values.filter(value =>
    typeof value === 'number' && Number.isFinite(value)
  );

  return valid.length ? Math.max(...valid) : null;
}

function windMph(value) {
  if (typeof value !== 'string') return null;

  const numbers = value.match(/\d+(\.\d+)?/g);

  if (!numbers || !numbers.length) return null;

  return average(numbers.map(Number));
}

function precipitationLevel(probability) {
  if (probability === null) return 'Unknown';
  if (probability >= 70) return 'Heavy';
  if (probability >= 30) return 'Mild';
  return 'No';
}

function visibilityMilesAt(records, isoTime) {
  const target = Date.parse(isoTime);

  if (!Number.isFinite(target)) return null;

  for (const record of records || []) {
    const [startText, durationText] =
      String(record.validTime || '').split('/');

    const start = Date.parse(startText);

    const match =
      /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$/.exec(
        durationText || ''
      );

    if (!Number.isFinite(start) || !match) continue;

    const days = Number(match[1] || 0);
    const hours = Number(match[2] || 0);
    const minutes = Number(match[3] || 0);

    const duration =
      (days * 24 * 60 + hours * 60 + minutes) * 60000;

    if (duration <= 0) continue;

    const end = start + duration;

    if (
      target >= start &&
      target < end &&
      typeof record.value === 'number' &&
      Number.isFinite(record.value) &&
      record.value >= 0
    ) {
      return Math.round(record.value / 1609.344 * 10) / 10;
    }
  }

  return null;
}

function openMeteoValueAt(records, isoTime, field) {
  const target = Date.parse(isoTime);
  if (!Number.isFinite(target)) return null;

  const record = (records || []).find(item =>
    Date.parse(item.time) === target
  );

  const value = record?.[field];
  return typeof value === 'number' &&
    Number.isFinite(value) && value >= 0
      ? value
      : null;
}

function summarizePeriod(periods, label, visibilityRecords = [], openMeteoRecords = []) {
  if (!periods.length) {
    return {
      label,
      available: false,
      temperature: null,
      temperatureUnit: 'F',
      windSpeedMph: null,
      visibility: null,
      uvIndex: null,
      humidity: null,
      rain: 'Unknown',
      snow: 'Unknown',
      precipitationProbability: null,
      shortForecast: 'Forecast not available',
      roadConditions: null,
      clothingAdvice: null,
      accessoriesAdvice: null
    };
  }

  const visibility = average(
    periods.map(p =>
      visibilityMilesAt(visibilityRecords, p.startTime)
    )
  );

  const openMeteoVisibility = average(
    periods.map(p => {
      const meters = openMeteoValueAt(
        openMeteoRecords, p.startTime, 'visibility'
      );
      return meters === null ? null : meters / 1609.344;
    })
  );

  const uvIndex = average(
    periods.map(p =>
      openMeteoValueAt(openMeteoRecords, p.startTime, 'uvIndex')
    )
  );

  const finalVisibility =
    visibility === null ? openMeteoVisibility : visibility;

  const temperature = average(
    periods.map(p => p.temperature)
  );

  const windSpeed = average(
    periods.map(p => windMph(p.windSpeed))
  );

  const humidity = average(
    periods.map(p => p.relativeHumidity?.value ?? null)
  );

  const precipitationProbability = maximum(
    periods.map(p =>
      p.probabilityOfPrecipitation?.value ?? null
    )
  );

  const descriptions = periods
    .map(p => p.shortForecast || '')
    .filter(Boolean);

  const description = descriptions[0] || 'Not available';

  const snowMentioned = descriptions.some(text =>
    /\bsnow\b|\bflurries\b|\bsleet\b/i.test(text)
  );

  const rainMentioned = descriptions.some(text =>
    /\brain\b|\bshowers\b|\bdrizzle\b/i.test(text)
  );

  return {
    label,
    available: true,
    temperature,
    temperatureUnit: 'F',
    windSpeedMph: windSpeed,
    visibility: finalVisibility,
    uvIndex,
    humidity,
    rain: rainMentioned
      ? precipitationLevel(precipitationProbability)
      : 'No',
    snow: snowMentioned
      ? precipitationLevel(precipitationProbability)
      : 'No',
    precipitationProbability,
    shortForecast: description,
    roadConditions: null,
    clothingAdvice: null,
    accessoriesAdvice: null
  };
}

function periodsForDate(periods, date, timezone, start, end) {
  return periods.filter(period => {
    if (!period.startTime) return false;

    return localDate(period.startTime, timezone) === date &&
      localHour(period.startTime, timezone) >= start &&
      localHour(period.startTime, timezone) <= end;
  });
}

async function getWeather(zip) {
  const locationData = await fetchJson(
    `${ZIP_API}/us/${encodeURIComponent(zip)}`
  );

  if (!locationData.places?.length) {
    const error = new Error('ZIP code not found');
    error.status = 404;
    throw error;
  }

  const place = locationData.places[0];
  const latitude = Number(place.latitude);
  const longitude = Number(place.longitude);

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new Error('Invalid location coordinates');
  }

  const pointData = await fetchJson(
    `${NWS_API}/points/${latitude},${longitude}`
  );

  const properties = pointData.properties || {};
  const hourlyUrl = properties.forecastHourly;
  const timezone = properties.timeZone;

  if (!hourlyUrl || !timezone) {
    throw new Error('Hourly forecast or timezone unavailable');
  }

  const hourlyData = await fetchJson(hourlyUrl);
  const periods = hourlyData.properties?.periods || [];

  let visibilityRecords = [];

  if (properties.forecastGridData) {
    try {
      const gridData = await fetchJson(
        properties.forecastGridData
      );

      const visibility = gridData.properties?.visibility;

      if (visibility?.uom === 'wmoUnit:m') {
        visibilityRecords = visibility.values || [];
      }
    } catch (error) {
      log('visibility_unavailable', {
        message: error.message
      });
    }
  }

  let openMeteoRecords = [];

  try {
    const url = new URL('https://api.open-meteo.com/v1/forecast');
    url.searchParams.set('latitude', String(latitude));
    url.searchParams.set('longitude', String(longitude));
    url.searchParams.set('hourly', 'visibility,uv_index');
    url.searchParams.set('forecast_days', '7');
    url.searchParams.set('timezone', 'GMT');

    const result = await fetchJson(url.toString());
    const hourly = result.hourly || {};

    openMeteoRecords = (hourly.time || []).map((time, index) => ({
      time: time + 'Z',
      visibility: hourly.visibility?.[index] ?? null,
      uvIndex: hourly.uv_index?.[index] ?? null
    }));
  } catch (error) {
    log('open_meteo_unavailable', { message: error.message });
  }

  return {
    zip,
    city: place['place name'],
    state: place.state,
    latitude,
    longitude,
    timezone,
    periods,
    visibilityRecords,
    openMeteoRecords,
    updatedAt: new Date().toISOString(),
    provider: 'National Weather Service',
    sourceUrl: hourlyUrl
  };
}

function selectWeather(data, date) {
  const morningPeriods = periodsForDate(
    data.periods, date, data.timezone, 6, 11
  );

  const nightPeriods = periodsForDate(
    data.periods, date, data.timezone, 18, 23
  );

  return {
    zip: data.zip,
    city: data.city,
    state: data.state,
    date,
    timezone: data.timezone,
    morning: summarizePeriod(
      morningPeriods, 'Morning',
      data.visibilityRecords, data.openMeteoRecords
    ),
    night: summarizePeriod(
      nightPeriods, 'Night',
      data.visibilityRecords, data.openMeteoRecords
    ),
    provider: data.provider,
    sourceUrl: data.sourceUrl,
    updatedAt: data.updatedAt
  };
}

app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'weather',
    time: new Date().toISOString()
  });
});

app.get('/weather/:zip', async (req, res) => {
  const zip = req.params.zip;
  const requestedDate = req.query.date;

  if (!validZip(zip)) {
    return res.status(400).json({
      error: 'ZIP code must contain exactly 5 numbers'
    });
  }

  if (requestedDate !== undefined && !validDate(requestedDate)) {
    return res.status(400).json({
      error: 'Date must use YYYY-MM-DD format'
    });
  }

  try {
    let weather = await readCache(zip);
    let source = 'cache';

    if (!weather) {
      weather = await getWeather(zip);
      await saveCache(zip, weather);
      source = 'live';
    }

    const today = todayInTimezone(weather.timezone);
    const date = requestedDate || today;

    if (!dateInRange(date, today)) {
      return res.status(400).json({
        error: 'Select a date within the next 7 days',
        today
      });
    }

    log('weather_requested', { zip, date, source });

    return res.json({
      ...selectWeather(weather, date),
      source
    });
  } catch (error) {
    log('weather_error', {
      zip,
      message: error.message
    });

    if (error.status === 404) {
      return res.status(404).json({
        error: 'ZIP code or forecast not found'
      });
    }

    return res.status(502).json({
      error: 'Weather service is temporarily unavailable'
    });
  }
});

if (require.main === module) {
  app.listen(PORT, '0.0.0.0', () => {
    log('weather_started', { port: PORT });
  });
}

module.exports = app;
