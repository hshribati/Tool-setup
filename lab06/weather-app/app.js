
'use strict';

const fs = require('fs');
const express = require('express');
const { Pool } = require('pg');
const { SSMClient, GetParameterCommand } = require('@aws-sdk/client-ssm');

const app = express();

const PORT = Number(process.env.PORT || 3000);
const ZIP_API = process.env.ZIP_API_BASE || 'https://api.zippopotam.us';
const NWS_API = process.env.NWS_API_BASE || 'https://api.weather.gov';

const USER_AGENT =
  process.env.NWS_USER_AGENT ||
  '(ITMO 544 weather lab, hshribati@hawk.illinoistech.edu)';

const DB_HOST = process.env.DB_HOST;
const DB_PORT = Number(process.env.DB_PORT || 5432);
const DB_NAME = process.env.DB_NAME || 'weather';
const DB_USER = process.env.DB_USER || 'weatherapp';

const DB_PASSWORD_PARAM =
  process.env.DB_PASSWORD_PARAM || '/itmo-444-544/db-password';

const DB_CA_FILE = process.env.DB_CA_FILE || '/opt/app/rds-ca.pem';
const CACHE_SECONDS = Number(process.env.CACHE_SECONDS || 600);
const DB_RETRY_MS = 30000;

const ssm = new SSMClient({
  region: process.env.AWS_REGION || 'us-east-2'
});

let pool = null;
let lastDbAttempt = 0;

function log(event, fields = {}) {
  console.log(JSON.stringify({
    time: new Date().toISOString(),
    event,
    ...fields
  }));
}

function validZip(zip) {
  return /^\d{5}$/.test(zip);
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

      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}`);
        error.status = response.status;

        if (response.status < 500 && response.status !== 429) {
          throw error;
        }

        lastError = error;
      } else {
        return await response.json();
      }
    } catch (error) {
      lastError = error;

      if (error.status && error.status < 500 && error.status !== 429) {
        throw error;
      }
    }

    if (attempt < attempts) {
      await new Promise(resolve => setTimeout(resolve, attempt * 500));
    }
  }

  throw lastError;
}

async function getDbPassword() {
  if (process.env.DB_PASSWORD) {
    return process.env.DB_PASSWORD;
  }

  const response = await ssm.send(
    new GetParameterCommand({
      Name: DB_PASSWORD_PARAM,
      WithDecryption: true
    })
  );

  return response.Parameter.Value;
}

async function getPool() {
  if (!DB_HOST) {
    return null;
  }

  if (pool) {
    return pool;
  }

  if (Date.now() - lastDbAttempt < DB_RETRY_MS) {
    return null;
  }

  lastDbAttempt = Date.now();

  try {
    const password = await getDbPassword();

    const ssl = process.env.DB_SSL === 'off'
      ? false
      : fs.existsSync(DB_CA_FILE)
        ? {
            ca: fs.readFileSync(DB_CA_FILE, 'utf8'),
            rejectUnauthorized: true
          }
        : {
            rejectUnauthorized: true
          };

    const candidate = new Pool({
      host: DB_HOST,
      port: DB_PORT,
      database: DB_NAME,
      user: DB_USER,
      password,
      ssl,
      connectionTimeoutMillis: 5000,
      idleTimeoutMillis: 30000,
      max: 5
    });

    candidate.on('error', error => {
      log('db_idle_error', { message: error.message });
    });

    await candidate.query(`
      CREATE TABLE IF NOT EXISTS weather_cache (
        zip VARCHAR(5) PRIMARY KEY,
        data JSONB NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    pool = candidate;
    log('db_connected');
    return pool;
  } catch (error) {
    log('db_connection_failed', { message: error.message });
    return null;
  }
}

async function readCache(zip) {
  try {
    const db = await getPool();
    if (!db) return null;

    const result = await db.query(
      'SELECT data, updated_at FROM weather_cache WHERE zip = $1',
      [zip]
    );

    if (result.rows.length === 0) {
      return null;
    }

    const row = result.rows[0];
    const ageSeconds =
      (Date.now() - new Date(row.updated_at).getTime()) / 1000;

    if (ageSeconds > CACHE_SECONDS) {
      return null;
    }

    return row.data;
  } catch (error) {
    log('cache_read_failed', { message: error.message });
    return null;
  }
}

async function saveCache(zip, data) {
  try {
    const db = await getPool();
    if (!db) return;

    await db.query(
      `INSERT INTO weather_cache (zip, data, updated_at)
       VALUES ($1, $2::jsonb, NOW())
       ON CONFLICT (zip)
       DO UPDATE SET
         data = EXCLUDED.data,
         updated_at = NOW()`,
      [zip, JSON.stringify(data)]
    );
  } catch (error) {
    log('cache_write_failed', { message: error.message });
  }
}

async function getWeather(zip) {
  const locationData = await fetchJson(
    `${ZIP_API}/us/${encodeURIComponent(zip)}`
  );

  if (!locationData.places || locationData.places.length === 0) {
    throw new Error('No location found for ZIP code');
  }

  const place = locationData.places[0];
  const latitude = Number(place.latitude);
  const longitude = Number(place.longitude);

  const points = await fetchJson(
    `${NWS_API}/points/${latitude},${longitude}`
  );

  if (!points.properties || !points.properties.forecast) {
    throw new Error('Forecast URL not found');
  }

  const forecast = await fetchJson(points.properties.forecast);
  const periods = forecast.properties?.periods || [];

  return {
    zip,
    city: place['place name'],
    state: place.state,
    latitude,
    longitude,
    forecast: periods.slice(0, 7).map(period => ({
      name: period.name,
      temperature: period.temperature,
      temperatureUnit: period.temperatureUnit,
      windSpeed: period.windSpeed,
      windDirection: period.windDirection,
      shortForecast: period.shortForecast,
      detailedForecast: period.detailedForecast
    })),
    updatedAt: new Date().toISOString()
  };
}

app.get('/health', async (req, res) => {
  res.json({
    status: 'ok',
    service: 'weather',
    time: new Date().toISOString()
  });
});

app.get('/weather/:zip', async (req, res) => {
  const zip = req.params.zip;

  if (!validZip(zip)) {
    return res.status(400).json({
      error: 'ZIP code must contain exactly 5 numbers'
    });
  }

  try {
    const cached = await readCache(zip);

    if (cached) {
      log('weather_cache_hit', { zip });

      return res.json({
        ...cached,
        source: 'cache'
      });
    }

    const weather = await getWeather(zip);
    await saveCache(zip, weather);

    log('weather_fetched', { zip });

    return res.json({
      ...weather,
      source: 'live'
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

app.get('/history', async (req, res) => {
  try {
    const db = await getPool();

    if (!db) {
      return res.status(503).json({
        error: 'Database is unavailable',
        history: []
      });
    }

    const result = await db.query(
      `SELECT zip, data, updated_at
       FROM weather_cache
       ORDER BY updated_at DESC
       LIMIT 20`
    );

    return res.json({
      history: result.rows
    });
  } catch (error) {
    log('history_error', { message: error.message });

    return res.status(503).json({
      error: 'Unable to load weather history',
      history: []
    });
  }
});

if (require.main === module) {
  app.listen(PORT, '0.0.0.0', () => {
    log('weather_started', { port: PORT });
  });
}

module.exports = app;

