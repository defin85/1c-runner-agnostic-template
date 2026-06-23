#!/usr/bin/env node
import crypto from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const DEFAULT_TIMEOUT_SECONDS = 120;
const DEFAULT_ROUTE = 'Fixture Route';
const DEFAULT_SECTION = 'FixtureSection';
const DEFAULT_BROWSER_MODE = 'headless';
const SUMMARY_SCHEMA_VERSION = 1;
const EXIT_BY_STATUS = {
  success: 0,
  skipped: 0,
  unavailable: 0,
  failed: 1,
  timeout: 124,
};
const SENSITIVE_QUERY_NAMES = /(?:password|passwd|pwd|token|auth|session|seance|secret|ticket|key|cookie)/i;

const scriptPath = fileURLToPath(import.meta.url);
const projectRoot = path.resolve(path.dirname(scriptPath), '..', '..');

main().catch((error) => {
  process.stderr.write(`${redactText(error?.stack || error?.message || String(error), [])}\n`);
  process.exit(1);
});

async function main() {
  const cli = parseArgs(process.argv.slice(2));
  if (cli.help) {
    printUsage();
    return;
  }
  if (!cli.profile || !cli.runRoot) {
    process.stderr.write('error: --profile and --run-root are required\n');
    printUsage();
    process.exit(2);
  }

  const runRoot = path.resolve(cli.runRoot);
  await mkdir(runRoot, { recursive: true });
  const stdoutLog = path.join(runRoot, 'stdout.log');
  const stderrLog = path.join(runRoot, 'stderr.log');
  const summaryJson = path.join(runRoot, 'summary.json');
  const startedAt = new Date();
  const stdout = [];
  const stderr = [];
  let sensitiveValues = [];
  let browserModule = null;

  const writeLogs = async () => {
    await writeFile(stdoutLog, `${stdout.join('\n')}${stdout.length ? '\n' : ''}`, 'utf8');
    await writeFile(stderrLog, `${stderr.join('\n')}${stderr.length ? '\n' : ''}`, 'utf8');
  };
  const out = (message) => stdout.push(redactText(message, sensitiveValues));
  const err = (message) => stderr.push(redactText(message, sensitiveValues));

  let profile = null;
  let summary = null;
  try {
    profile = await readJson(path.resolve(cli.profile));
    sensitiveValues = collectSensitiveValues(profile);
    const resolved = resolveDiagnosticConfig({ cli, profile, runRoot, summaryJson, stdoutLog, stderrLog });
    sensitiveValues = collectSensitiveValues(profile, resolved.auth);

    summary = buildBaseSummary({
      cli,
      profile,
      resolved,
      runRoot,
      summaryJson,
      stdoutLog,
      stderrLog,
      startedAt,
    });

    if (cli.skipReason) {
      summary.status = 'skipped';
      summary.statusReason = { class: 'skipped', message: cli.skipReason };
      out(`diagnostic skipped: ${cli.skipReason}`);
      return await finish(summary);
    }

    const preflight = preflightDiagnostic(resolved);
    if (preflight) {
      summary.status = 'unavailable';
      summary.statusReason = preflight;
      err(preflight.message);
      return await finish(summary);
    }

    if (resolved.mode !== 'inspect') {
      summary.status = 'failed';
      summary.statusReason = {
        class: 'inspect-only',
        message: `unsupported diagnostic mode: ${resolved.mode}`,
      };
      summary.mode.effective = 'inspect';
      summary.evidence.extraction = {
        status: 'unsupported',
        message: 'mutating replay is not allowed by the current diagnostic contract',
      };
      err(summary.statusReason.message);
      return await finish(summary);
    }

    out(`source_run_root=${resolved.source.runRoot || '<manual>'}`);
    out(`target_publication=${resolved.target.publication.url}`);
    out(`route=${resolved.route}`);
    out(`backend=${resolved.backend}`);

    const runPromise = runBackend({
      resolved,
      summary,
      setBrowserModule: (module) => {
        browserModule = module;
      },
      out,
      err,
    });
    const timeoutPromise = sleep(resolved.budget.timeoutSeconds * 1000).then(() => {
      const timeoutError = new Error(`browser diagnostic exceeded ${resolved.budget.timeoutSeconds}s`);
      timeoutError.code = 'DIAGNOSTIC_TIMEOUT';
      throw timeoutError;
    });

    try {
      await Promise.race([runPromise, timeoutPromise]);
    } catch (error) {
      if (error?.code === 'DIAGNOSTIC_TIMEOUT') {
        summary.status = 'timeout';
        summary.statusReason = {
          class: 'timeout',
          message: error.message,
        };
        err(error.message);
        if (browserModule?.disconnect) {
          await browserModule.disconnect().catch(() => {});
        }
      } else {
        applyBackendError(summary, error);
        err(error?.message || String(error));
      }
    }

    return await finish(summary);
  } catch (error) {
    const fallback = summary || buildFallbackSummary({
      cli,
      profile,
      runRoot,
      summaryJson,
      stdoutLog,
      stderrLog,
      startedAt,
    });
    fallback.status = 'failed';
    fallback.statusReason = {
      class: 'internal-error',
      message: error?.message || String(error),
    };
    err(error?.stack || error?.message || String(error));
    return await finish(fallback);
  }

  async function finish(rawSummary) {
    const finishedAt = new Date();
    rawSummary.finishedAt = finishedAt.toISOString();
    rawSummary.durationSeconds = roundSeconds(finishedAt - startedAt);
    rawSummary = sanitizeObject(rawSummary, sensitiveValues);
    await writeFile(summaryJson, `${JSON.stringify(rawSummary, null, 2)}\n`, 'utf8');
    await writeLogs();
    process.stdout.write(`summary_json=${summaryJson}\n`);
    process.exit(EXIT_BY_STATUS[rawSummary.status] ?? 1);
  }
}

function parseArgs(argv) {
  const cli = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    switch (arg) {
      case '--profile':
        cli.profile = requireValue(argv, ++index, arg);
        break;
      case '--run-root':
        cli.runRoot = requireValue(argv, ++index, arg);
        break;
      case '--source-run-root':
        cli.sourceRunRoot = requireValue(argv, ++index, arg);
        break;
      case '--source-stage':
        cli.sourceStage = requireValue(argv, ++index, arg);
        break;
      case '--feature':
        cli.feature = requireValue(argv, ++index, arg);
        break;
      case '--scenario':
        cli.scenario = requireValue(argv, ++index, arg);
        break;
      case '--step':
        cli.step = requireValue(argv, ++index, arg);
        break;
      case '--web-url':
        cli.webUrl = requireValue(argv, ++index, arg);
        break;
      case '--section':
        cli.section = requireValue(argv, ++index, arg);
        break;
      case '--route':
        cli.route = requireValue(argv, ++index, arg);
        break;
      case '--timeout-seconds':
        cli.timeoutSeconds = requireValue(argv, ++index, arg);
        break;
      case '--backend':
        cli.backend = requireValue(argv, ++index, arg);
        break;
      case '--browser-mode':
        cli.browserMode = requireValue(argv, ++index, arg);
        break;
      case '--mode':
        cli.mode = requireValue(argv, ++index, arg);
        break;
      case '--skip-reason':
        cli.skipReason = requireValue(argv, ++index, arg);
        break;
      case '-h':
      case '--help':
        cli.help = true;
        break;
      default:
        throw new Error(`unknown argument: ${arg}`);
    }
  }
  return cli;
}

function requireValue(argv, index, flag) {
  if (index >= argv.length || argv[index].startsWith('--')) {
    throw new Error(`${flag} requires a value`);
  }
  return argv[index];
}

function printUsage() {
  process.stdout.write(`Usage: ./scripts/test/run-web-client-diagnostic.sh --profile <file> --run-root <dir> [options]

Options:
  --source-run-root <dir>      Vanessa or warm-service run-root to link
  --source-stage <id>          Source stage/capability id
  --feature <path>             Source feature path when known
  --scenario <name>            Source scenario name when known
  --step <text>                Source failed step when known
  --web-url <url>              Explicit web-client endpoint override
  --section <name>             Optional 1C command-interface section, default: ${DEFAULT_SECTION}
  --route <name>               Inspect-only command/form route, default: ${DEFAULT_ROUTE}
  --timeout-seconds <seconds>  Browser diagnostic budget, default: ${DEFAULT_TIMEOUT_SECONDS}
  --backend <name>             web-test or fixture
  --browser-mode <mode>        headless (default) or visible
  --mode <name>                inspect only in this implementation
  --skip-reason <text>         Write skipped summary without browser work
`);
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, 'utf8'));
}

function resolveDiagnosticConfig({ cli, profile, runRoot, summaryJson, stdoutLog, stderrLog }) {
  const capability = profile?.capabilities?.webClientDiagnostic || {};
  const profilePath = path.resolve(cli.profile);
  const sourceRunRoot = cli.sourceRunRoot ? path.resolve(cli.sourceRunRoot) : null;
  const envUrl = process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_WEB_URL || '';
  let endpoint = null;
  let endpointSource = null;

  if (cli.webUrl) {
    endpoint = cli.webUrl;
    endpointSource = 'cli';
  } else if (envUrl) {
    endpoint = envUrl;
    endpointSource = 'env:ONEC_WEB_CLIENT_DIAGNOSTIC_WEB_URL';
  } else if (capability.webUrlEnv) {
    endpointSource = `env:${capability.webUrlEnv}`;
    endpoint = process.env[capability.webUrlEnv] || '';
  } else if (capability.webUrl) {
    endpoint = capability.webUrl;
    endpointSource = 'profile';
  }

  const timeoutResolution = resolveTimeout(cli, capability);
  const auth = capability.authOverride || capability.auth || profile?.infobase?.auth || {};
  const authSource = capability.authOverride
    ? 'capabilities.webClientDiagnostic.authOverride'
    : capability.auth
      ? 'capabilities.webClientDiagnostic.auth'
      : 'infobase.auth';
  const section = cli.section || process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_SECTION || capability.section || DEFAULT_SECTION;
  const route = cli.route || process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_ROUTE || capability.route || DEFAULT_ROUTE;
  const backend = cli.backend || process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_BACKEND || capability.backend || 'web-test';
  const browserDisplay = resolveBrowserDisplay(cli, capability);
  const mode = cli.mode || process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_MODE || capability.mode || 'inspect';
  const publication = buildPublication(endpoint, endpointSource);
  const sourceSummary = readSourceSummarySync(sourceRunRoot);
  const sameInfobase = checkSameInfobase(profile, capability, endpoint);

  return {
    capability,
    webUrl: endpoint,
    source: {
      runRoot: sourceRunRoot,
      summaryJson: sourceRunRoot ? path.join(sourceRunRoot, 'summary.json') : null,
      stage: cli.sourceStage || null,
      feature: cli.feature || null,
      scenario: cli.scenario || null,
      step: cli.step || null,
      verdict: sourceSummary,
    },
    target: {
      profile: {
        path: profilePath,
        name: profile?.profileName || null,
      },
      infobase: {
        mode: profile?.infobase?.mode || null,
        server: profile?.infobase?.server || null,
        ref: profile?.infobase?.ref || null,
        filePath: profile?.infobase?.filePath || null,
        authMode: profile?.infobase?.auth?.mode || null,
      },
      publication,
      sameInfobase,
      auth: {
        mode: auth?.mode || null,
        source: authSource,
        userConfigured: Boolean(auth?.user),
        passwordEnv: auth?.passwordEnv || null,
        passwordAvailable: Boolean(auth?.passwordEnv && process.env[auth.passwordEnv]),
      },
    },
    auth,
    section,
    route,
    backend,
    browserDisplay,
    mode,
    budget: timeoutResolution,
    artifacts: {
      summaryJson,
      stdoutLog,
      stderrLog,
      screenshot: path.join(runRoot, 'screenshot.png'),
      domSnapshot: path.join(runRoot, 'dom.html'),
    },
  };
}

function buildPublication(endpoint, endpointSource) {
  return {
    url: endpoint ? redactUrl(endpoint) : null,
    source: endpointSource,
    configured: Boolean(endpoint),
    credentialBearing: endpoint ? urlHasCredentials(endpoint) : false,
    identityHash: endpoint ? stableHash(stripUrlCredentialsAndSensitiveQuery(endpoint)) : null,
  };
}

function resolveTimeout(cli, capability) {
  let timeoutSeconds = DEFAULT_TIMEOUT_SECONDS;
  let source = 'default';
  if (cli.timeoutSeconds) {
    timeoutSeconds = cli.timeoutSeconds;
    source = 'cli';
  } else if (process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_TIMEOUT_SECONDS) {
    timeoutSeconds = process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_TIMEOUT_SECONDS;
    source = 'env:ONEC_WEB_CLIENT_DIAGNOSTIC_TIMEOUT_SECONDS';
  } else if (capability.timeoutSeconds != null) {
    timeoutSeconds = capability.timeoutSeconds;
    source = 'profile';
  }

  const parsed = Number(timeoutSeconds);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`web-client diagnostic timeout must be a positive integer, got: ${timeoutSeconds}`);
  }

  return {
    timeoutSeconds: parsed,
    defaultSeconds: DEFAULT_TIMEOUT_SECONDS,
    override: {
      used: source !== 'default',
      source,
    },
  };
}

function resolveBrowserDisplay(cli, capability) {
  let raw = DEFAULT_BROWSER_MODE;
  let source = 'default';
  if (cli.browserMode) {
    raw = cli.browserMode;
    source = 'cli';
  } else if (process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_BROWSER_MODE) {
    raw = process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_BROWSER_MODE;
    source = 'env:ONEC_WEB_CLIENT_DIAGNOSTIC_BROWSER_MODE';
  } else if (capability.browserMode) {
    raw = capability.browserMode;
    source = 'profile';
  }

  const normalized = String(raw || '').trim().toLowerCase();
  if (['headless', 'hidden', 'background'].includes(normalized)) {
    return { mode: 'headless', headless: true, source, valid: true };
  }
  if (['visible', 'headed', 'debug'].includes(normalized)) {
    return { mode: 'visible', headless: false, source, valid: true };
  }
  return { mode: normalized || null, headless: null, source, valid: false };
}

function readSourceSummarySync(sourceRunRoot) {
  if (!sourceRunRoot) {
    return null;
  }
  const summaryPath = path.join(sourceRunRoot, 'summary.json');
  const bootstrapSummaryPath = path.join(sourceRunRoot, 'bootstrap-summary.json');
  const candidatePath = existsSync(summaryPath)
    ? summaryPath
    : existsSync(bootstrapSummaryPath)
      ? bootstrapSummaryPath
      : summaryPath;
  if (!existsSync(candidatePath)) {
    return {
      status: null,
      exitCode: null,
      failureClassification: null,
      summaryJson: summaryPath,
      present: false,
    };
  }
  try {
    const data = JSON.parse(readFileSync(candidatePath, 'utf8'));
    return {
      status: data.status ?? null,
      exitCode: data.exit_code ?? data.exitCode ?? null,
      failureClassification: data.failure?.classification ?? data.failure_classification ?? null,
      summaryJson: candidatePath,
      present: true,
    };
  } catch (error) {
    return {
      status: null,
      exitCode: null,
      failureClassification: 'source summary unreadable',
      summaryJson: candidatePath,
      present: false,
      error: error.message,
    };
  }
}

function checkSameInfobase(profile, capability, endpoint) {
  if (capability.sameInfobaseConfirmed === true) {
    return {
      status: 'confirmed-by-profile',
      reason: 'capabilities.webClientDiagnostic.sameInfobaseConfirmed=true',
    };
  }
  const expectedRef = capability.infobaseRef || profile?.infobase?.ref || '';
  if (!expectedRef || !endpoint) {
    return {
      status: 'unknown',
      reason: 'profile has no comparable infobase ref or publication endpoint is missing',
    };
  }
  let pathname = '';
  try {
    pathname = new URL(endpoint).pathname.toLowerCase();
  } catch {
    return {
      status: 'unavailable',
      reason: 'publication endpoint is not a valid URL',
    };
  }
  if (pathname.includes(expectedRef.toLowerCase())) {
    return {
      status: 'matched',
      reason: 'publication path contains profile infobase ref',
    };
  }
  return {
    status: 'mismatch',
    reason: `publication path does not contain expected infobase ref: ${expectedRef}`,
  };
}

function preflightDiagnostic(resolved) {
  const capability = resolved.capability || {};
  if (capability.unsupportedReason) {
    return {
      class: 'profile-unsupported',
      message: capability.unsupportedReason,
    };
  }
  if (!resolved.target.publication.configured) {
    return {
      class: 'publication',
      message: 'capabilities.webClientDiagnostic.webUrl/webUrlEnv or explicit --web-url is required',
    };
  }
  if (resolved.target.sameInfobase.status === 'mismatch' || resolved.target.sameInfobase.status === 'unavailable') {
    return {
      class: 'infobase-identity',
      message: resolved.target.sameInfobase.reason,
    };
  }
  if (resolved.auth?.mode === 'user-password' && resolved.auth?.passwordEnv && !process.env[resolved.auth.passwordEnv]) {
    return {
      class: 'auth',
      message: `required auth password env var is not set: ${resolved.auth.passwordEnv}`,
    };
  }
  if (!resolved.browserDisplay.valid) {
    return {
      class: 'browser-display',
      message: `unsupported browser mode: ${resolved.browserDisplay.mode || '<empty>'}; expected headless or visible`,
    };
  }
  return null;
}

function buildBaseSummary({ cli, profile, resolved, runRoot, summaryJson, stdoutLog, stderrLog, startedAt }) {
  return {
    schemaVersion: SUMMARY_SCHEMA_VERSION,
    status: 'failed',
    statusReason: null,
    generatedAt: startedAt.toISOString(),
    startedAt: startedAt.toISOString(),
    finishedAt: null,
    durationSeconds: null,
    runRoot,
    source: resolved.source,
    target: resolved.target,
    browser: {
      backend: resolved.backend,
      status: 'not-started',
      name: null,
      version: null,
      display: resolved.browserDisplay,
      auth: {
        loginPageDetected: null,
        loginAttempted: false,
        status: 'not-checked',
      },
    },
    mode: {
      requested: resolved.mode,
      effective: resolved.mode,
      inspectOnly: true,
      allowedActions: ['open', 'login', 'navigate', 'filter', 'read', 'screenshot', 'dom-snapshot'],
      disallowedActions: ['create', 'write', 'post', 'save', 'delete', 'commit'],
    },
    budget: resolved.budget,
    evidence: {
      section: resolved.section,
      route: resolved.route,
      navigation: null,
      currentUrl: null,
      pageTitle: null,
      form: null,
      tables: [],
      filters: [],
      selectedRows: [],
      extraction: {
        status: 'not-found',
        message: 'browser evidence has not been captured yet',
      },
      artifacts: {
        screenshot: null,
        domSnapshot: null,
      },
    },
    verdictBoundary: {
      diagnosticOnly: true,
      sourceVerdictPreserved: true,
      releaseVerdictSource: 'Vanessa/release stage summary',
      note: 'Browser evidence is post-failure diagnostic against the same infobase data, not a live attach to the Vanessa TestClient session.',
    },
    redaction: {
      applied: true,
      placeholders: ['__REDACTED_SECRET__', '__REDACTED_CREDENTIALS__', '__REDACTED_QUERY_VALUE__', '__REDACTED_COOKIE__'],
      screenshotAndDomMayContainBusinessData: true,
    },
    artifacts: {
      summaryJson,
      stdoutLog,
      stderrLog,
    },
    environment: {
      host: os.hostname(),
      platform: os.platform(),
    },
    profileContract: {
      capabilityPath: 'capabilities.webClientDiagnostic',
      publishHttpMaterialized: false,
      profileName: profile?.profileName || null,
      explicitCliOverride: Boolean(cli.webUrl || cli.timeoutSeconds || cli.backend || cli.route),
    },
  };
}

function buildFallbackSummary({ cli, profile, runRoot, summaryJson, stdoutLog, stderrLog, startedAt }) {
  const resolved = {
    source: {
      runRoot: cli.sourceRunRoot ? path.resolve(cli.sourceRunRoot) : null,
      summaryJson: cli.sourceRunRoot ? path.join(path.resolve(cli.sourceRunRoot), 'summary.json') : null,
      stage: cli.sourceStage || null,
      feature: cli.feature || null,
      scenario: cli.scenario || null,
      step: cli.step || null,
      verdict: null,
    },
    target: {
      profile: {
        path: cli.profile ? path.resolve(cli.profile) : null,
        name: profile?.profileName || null,
      },
      infobase: {},
      publication: {
        url: null,
        source: null,
        configured: false,
        credentialBearing: false,
        identityHash: null,
      },
      sameInfobase: {
        status: 'unknown',
        reason: 'fallback summary',
      },
      auth: {},
    },
    backend: cli.backend || 'web-test',
    mode: cli.mode || 'inspect',
    section: cli.section || DEFAULT_SECTION,
    route: cli.route || DEFAULT_ROUTE,
    browserDisplay: {
      mode: cli.browserMode || DEFAULT_BROWSER_MODE,
      headless: (cli.browserMode || DEFAULT_BROWSER_MODE) !== 'visible',
      source: cli.browserMode ? 'cli' : 'default',
      valid: true,
    },
    budget: {
      timeoutSeconds: DEFAULT_TIMEOUT_SECONDS,
      defaultSeconds: DEFAULT_TIMEOUT_SECONDS,
      override: {
        used: false,
        source: 'default',
      },
    },
  };
  return buildBaseSummary({ cli, profile, resolved, runRoot, summaryJson, stdoutLog, stderrLog, startedAt });
}

async function runBackend({ resolved, summary, setBrowserModule, out, err }) {
  switch (resolved.backend) {
    case 'fixture':
      return runFixtureBackend({ resolved, summary, out, err });
    case 'web-test':
    case 'playwright-web-test':
      return runWebTestBackend({ resolved, summary, setBrowserModule, out, err });
    default:
      summary.status = 'unavailable';
      summary.statusReason = {
        class: 'browser-automation',
        message: `unsupported browser diagnostic backend: ${resolved.backend}`,
      };
      return;
  }
}

async function runFixtureBackend({ resolved, summary }) {
  if (process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_ALLOW_FIXTURE_BACKEND !== '1') {
    summary.status = 'unavailable';
    summary.statusReason = {
      class: 'browser-automation',
      message: 'fixture backend is disabled outside contract tests',
    };
    return;
  }

  const delayMs = Number(process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_FIXTURE_DELAY_MS || '0');
  if (delayMs > 0) {
    await sleep(delayMs);
  }

  const fixtureStatus = process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_FIXTURE_STATUS || 'success';
  summary.browser.status = 'ready';
  summary.browser.name = 'fixture';
  summary.browser.version = 'contract-test';
  summary.evidence.currentUrl = resolved.target.publication.url;
  summary.evidence.pageTitle = process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_FIXTURE_TITLE || 'Fixture 1C web client';
  summary.evidence.form = {
    title: resolved.route,
    identity: 'fixture-form',
    state: {
      activeSection: 'Fixture',
      activeTab: resolved.route,
    },
  };
  summary.evidence.tables = [{
    id: 'fixture-table',
    columns: ['Номер', 'Статус'],
    rows: [{ 'Номер': 'DL-001', 'Статус': 'fixture' }],
    selectedRowIndex: 0,
    extraction: {
      status: 'success',
      message: null,
    },
  }];
  summary.evidence.extraction = {
    status: 'success',
    message: null,
  };
  summary.status = fixtureStatus === 'failed' ? 'failed' : 'success';
  summary.statusReason = fixtureStatus === 'failed'
    ? { class: 'fixture-failure', message: 'fixture backend requested failure' }
    : { class: 'captured', message: 'fixture evidence captured' };
}

async function runWebTestBackend({ resolved, summary, setBrowserModule, out }) {
  const backendPath = process.env.ONEC_WEB_CLIENT_DIAGNOSTIC_WEB_TEST_BACKEND_PATH
    || path.join(projectRoot, 'automation/vendor/cc-1c-skills/skills/web-test/scripts/browser.mjs');
  if (!existsSync(backendPath)) {
    summary.status = 'unavailable';
    summary.statusReason = {
      class: 'browser-automation',
      message: `vendored web-test backend is missing: ${backendPath}`,
    };
    return;
  }

  let browser = null;
  try {
    browser = await import(pathToFileURL(backendPath).href);
  } catch (error) {
    summary.status = 'unavailable';
    summary.statusReason = {
      class: 'browser-automation',
      message: classifyImportError(error),
    };
    return;
  }
  setBrowserModule(browser);

  try {
    summary.browser.status = 'starting';
    await browser.connect(resolved.webUrl, { headless: resolved.browserDisplay.headless });
    summary.browser.status = 'ready';
    await performWebClientLoginIfNeeded({ browser, resolved, summary, out });
    if (typeof browser.closeStartupModals === 'function') {
      await browser.closeStartupModals();
    }

    let formState = null;
    if (resolved.section) {
      const navigation = await browser.navigateSection(resolved.section);
      summary.evidence.navigation = normalizeNavigationState(navigation, resolved.section);
    }
    if (resolved.route) {
      formState = await browser.openCommand(resolved.route);
    } else {
      formState = await browser.getFormState();
    }

    const page = browser.getPage();
    summary.evidence.currentUrl = redactUrl(page.url());
    summary.evidence.pageTitle = await page.title();
    summary.evidence.form = normalizeFormState(formState);

    await captureDomSnapshot(page, resolved.artifacts.domSnapshot);
    summary.evidence.artifacts.domSnapshot = {
      path: resolved.artifacts.domSnapshot,
      capturedAt: new Date().toISOString(),
    };

    const screenshot = await browser.screenshot();
    await writeFile(resolved.artifacts.screenshot, screenshot);
    summary.evidence.artifacts.screenshot = {
      path: resolved.artifacts.screenshot,
      capturedAt: new Date().toISOString(),
    };

    summary.evidence.tables = [await readVisibleTable(browser)];
    summary.evidence.extraction = summarizeExtraction(summary.evidence.tables, summary.evidence.form);
    summary.status = 'success';
    summary.statusReason = {
      class: 'captured',
      message: 'browser evidence captured',
    };
  } catch (error) {
    await captureFailureArtifacts({ browser, resolved, summary });
    applyBackendError(summary, error);
  } finally {
    await browser.disconnect().catch(() => {});
  }
}

function normalizeNavigationState(value, requestedSection) {
  return {
    requestedSection,
    activeSection: value?.sections?.find((section) => section?.active)?.name || null,
    sections: Array.isArray(value?.sections)
      ? value.sections.map((section) => section?.name).filter(Boolean).slice(0, 80)
      : [],
    commands: Array.isArray(value?.commands)
      ? value.commands.map((command) => command?.name).filter(Boolean).slice(0, 120)
      : [],
  };
}

async function performWebClientLoginIfNeeded({ browser, resolved, summary, out }) {
  const page = browser.getPage();
  const authState = summary.browser.auth || {};
  summary.browser.auth = {
    loginPageDetected: false,
    loginAttempted: false,
    status: 'not-required',
    ...authState,
  };

  const loginLocator = page.locator('#authWindow_basic_login');
  const loginVisible = await loginLocator.isVisible({ timeout: 2000 }).catch(() => false);
  summary.browser.auth.loginPageDetected = loginVisible;
  if (!loginVisible) {
    summary.browser.auth.status = 'not-required';
    return;
  }

  const password = resolved.auth?.passwordEnv ? process.env[resolved.auth.passwordEnv] : '';
  if (resolved.auth?.mode !== 'user-password' || !resolved.auth?.user || !password) {
    summary.browser.auth.status = 'failed';
    throw new Error('web login page is visible but user-password auth is not fully configured');
  }

  summary.browser.auth.loginAttempted = true;
  summary.browser.auth.status = 'in-progress';
  out?.(`web_login=attempted user=${resolved.auth.user}`);
  await loginLocator.fill(resolved.auth.user);
  await page.locator('#authWindow_basic_password').fill(password);
  await page.locator('#authWindow_basic_okButton').click();
  await page.waitForSelector('#themesCell_theme_0', {
    timeout: Math.min(Math.max(resolved.budget.timeoutSeconds * 1000, 10000), 90000),
  });
  await page.waitForTimeout(5000);
  summary.browser.auth.status = 'success';
  out?.('web_login=success');
}

async function captureFailureArtifacts({ browser, resolved, summary }) {
  let page = null;
  try {
    page = browser.getPage();
  } catch {
    return;
  }

  try {
    summary.evidence.currentUrl = redactUrl(page.url());
    summary.evidence.pageTitle = await page.title();
  } catch {}

  try {
    await captureDomSnapshot(page, resolved.artifacts.domSnapshot);
    summary.evidence.artifacts.domSnapshot = {
      path: resolved.artifacts.domSnapshot,
      capturedAt: new Date().toISOString(),
    };
  } catch {}

  try {
    const screenshot = await browser.screenshot();
    await writeFile(resolved.artifacts.screenshot, screenshot);
    summary.evidence.artifacts.screenshot = {
      path: resolved.artifacts.screenshot,
      capturedAt: new Date().toISOString(),
    };
  } catch {
    try {
      await page.screenshot({ path: resolved.artifacts.screenshot, fullPage: true });
      summary.evidence.artifacts.screenshot = {
        path: resolved.artifacts.screenshot,
        capturedAt: new Date().toISOString(),
      };
    } catch {}
  }
}

async function captureDomSnapshot(page, targetPath) {
  const html = await page.evaluate(() => document.documentElement.outerHTML);
  await writeFile(targetPath, html, 'utf8');
}

async function readVisibleTable(browser) {
  try {
    const table = await browser.readTable({ maxRows: 20 });
    const rows = Array.isArray(table?.rows) ? table.rows.slice(0, 20).map(limitObject) : [];
    return {
      id: 'visible-table',
      columns: Array.isArray(table?.columns) ? table.columns.slice(0, 40).map((value) => truncate(String(value), 200)) : [],
      rows,
      total: table?.total ?? rows.length,
      selectedRowIndex: table?.selectedRowIndex ?? null,
      extraction: {
        status: rows.length > 0 ? 'success' : 'empty',
        message: null,
      },
    };
  } catch (error) {
    return {
      id: 'visible-table',
      columns: [],
      rows: [],
      total: 0,
      selectedRowIndex: null,
      extraction: {
        status: /no form|not found/i.test(error?.message || '') ? 'not-found' : 'error',
        message: error?.message || String(error),
      },
    };
  }
}

function summarizeExtraction(tables, form) {
  if (!form) {
    return {
      status: 'error',
      message: 'form state was not captured',
    };
  }
  const tableStatuses = tables.map((table) => table.extraction?.status).filter(Boolean);
  if (tableStatuses.includes('success') || tableStatuses.includes('empty')) {
    return {
      status: 'success',
      message: null,
    };
  }
  if (tableStatuses.includes('not-found')) {
    return {
      status: 'partial',
      message: 'form was captured but visible table was not found',
    };
  }
  return {
    status: 'partial',
    message: 'form was captured with table extraction diagnostics',
  };
}

function normalizeFormState(formState) {
  if (!formState || typeof formState !== 'object') {
    return null;
  }
  return {
    title: formState.title || formState.caption || formState.formTitle || formState.activeTab || null,
    identity: formState.name || formState.form || formState.formName || null,
    state: limitObject(formState, 6000),
  };
}

function applyBackendError(summary, error) {
  const message = error?.message || String(error);
  const classification = classifyRuntimeError(message);
  summary.status = classification.status;
  summary.statusReason = {
    class: classification.className,
    message,
  };
  summary.browser.status = classification.status === 'unavailable' ? 'unavailable' : 'error';
  summary.evidence.extraction = {
    status: classification.status === 'unavailable' ? 'unsupported' : 'error',
    message,
  };
}

function classifyImportError(error) {
  const message = error?.message || String(error);
  if (/Cannot find package 'playwright'|ERR_MODULE_NOT_FOUND.*playwright/i.test(message)) {
    return 'Playwright dependency is not installed for the vendored web-test backend';
  }
  return message;
}

function classifyRuntimeError(message) {
  if (/playwright|browser executable|Executable doesn't exist|DISPLAY|xvfb|libnss|host system is missing/i.test(message)) {
    return { status: 'unavailable', className: 'browser-automation' };
  }
  if (/ERR_CONNECTION|ECONNREFUSED|ENOTFOUND|net::ERR|Navigation timeout|Timeout.*exceeded/i.test(message)) {
    return { status: 'unavailable', className: 'publication' };
  }
  if (/auth|401|403|login|password/i.test(message)) {
    return { status: 'unavailable', className: 'auth' };
  }
  return { status: 'failed', className: 'browser-diagnostic' };
}

function collectSensitiveValues(profile, auth = null) {
  const values = [];
  const addEnv = (envName) => {
    if (envName && process.env[envName]) {
      values.push(process.env[envName]);
    }
  };
  addEnv(profile?.infobase?.auth?.passwordEnv);
  addEnv(profile?.ibcmd?.auth?.passwordEnv);
  addEnv(profile?.ibcmd?.dbmsInfobase?.passwordEnv);
  addEnv(auth?.passwordEnv);
  addEnv('ONEC_WEB_CLIENT_DIAGNOSTIC_TOKEN');
  return [...new Set(values.filter((value) => typeof value === 'string' && value.length >= 3))];
}

function sanitizeObject(value, sensitiveValues) {
  if (value == null) {
    return value;
  }
  if (typeof value === 'string') {
    return redactText(value, sensitiveValues);
  }
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeObject(item, sensitiveValues));
  }
  if (typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, sanitizeObject(item, sensitiveValues)]));
  }
  return value;
}

function redactText(value, sensitiveValues = []) {
  let text = String(value ?? '');
  for (const secret of sensitiveValues) {
    if (secret) {
      text = text.split(secret).join('__REDACTED_SECRET__');
    }
  }
  text = text.replace(/(https?:\/\/)([^/\s:@]+):([^/\s@]+)@/gi, '$1__REDACTED_CREDENTIALS__@');
  text = text.replace(/([?&][^=\s&]*(?:password|passwd|pwd|token|auth|session|seance|secret|ticket|key|cookie)[^=\s&]*=)[^&\s]+/gi, '$1__REDACTED_QUERY_VALUE__');
  text = text.replace(/(Cookie:\s*)[^\r\n]+/gi, '$1__REDACTED_COOKIE__');
  return text;
}

function redactUrl(value) {
  try {
    const url = new URL(value);
    if (url.username || url.password) {
      url.username = '__REDACTED_USER__';
      url.password = '__REDACTED_PASSWORD__';
    }
    for (const key of [...url.searchParams.keys()]) {
      if (SENSITIVE_QUERY_NAMES.test(key)) {
        url.searchParams.set(key, '__REDACTED_QUERY_VALUE__');
      }
    }
    return url.toString();
  } catch {
    return redactText(value, []);
  }
}

function stripUrlCredentialsAndSensitiveQuery(value) {
  try {
    const url = new URL(value);
    url.username = '';
    url.password = '';
    for (const key of [...url.searchParams.keys()]) {
      if (SENSITIVE_QUERY_NAMES.test(key)) {
        url.searchParams.set(key, '__REDACTED_QUERY_VALUE__');
      }
    }
    return url.toString();
  } catch {
    return redactText(value, []);
  }
}

function urlHasCredentials(value) {
  try {
    const url = new URL(value);
    return Boolean(url.username || url.password);
  } catch {
    return false;
  }
}

function stableHash(value) {
  return crypto.createHash('sha256').update(String(value)).digest('hex').slice(0, 16);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function roundSeconds(ms) {
  return Math.round((ms / 1000) * 1000) / 1000;
}

function truncate(value, max = 500) {
  if (value.length <= max) {
    return value;
  }
  return `${value.slice(0, max)}...`;
}

function limitObject(value, maxJsonLength = 500) {
  if (value == null) {
    return value;
  }
  if (typeof value !== 'object') {
    return truncate(String(value), maxJsonLength);
  }
  const json = JSON.stringify(value);
  if (json.length <= maxJsonLength) {
    return value;
  }
  return {
    truncated: true,
    jsonSnippet: truncate(json, maxJsonLength),
  };
}
