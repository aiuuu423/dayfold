const SAMPLE_TEXT = "写下今天。Dayfold remembers.";
const PROBES = [
  { id: "family", localName: "HanziPen SC", family: "Probe HanziPen Family" },
  { id: "w3", localName: "HanziPenSC-W3", family: "Probe HanziPen W3" },
  { id: "w5", localName: "HanziPenSC-W5", family: "Probe HanziPen W5" },
];

function normalizeFamily(value) {
  return value.replaceAll('"', "").replaceAll("'", "");
}

function errorMessage(error) {
  try {
    const value = error instanceof Error ? error.message : error;
    const message =
      value === null || value === undefined ? "" : String(value);
    return message || "Unknown error";
  } catch {
    return "Unknown error";
  }
}

function renderSignature(family) {
  const canvas = document.createElement("canvas");
  canvas.width = 900;
  canvas.height = 120;
  const context = canvas.getContext("2d", { willReadFrequently: true });

  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#000";
  context.font = `48px "${family}", monospace`;
  context.textBaseline = "top";
  context.fillText(SAMPLE_TEXT, 8, 8);

  const metrics = context.measureText(SAMPLE_TEXT);
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
  let hash = 2166136261;

  for (let index = 3; index < pixels.length; index += 16) {
    hash ^= pixels[index];
    hash = Math.imul(hash, 16777619);
  }

  return {
    width: Number(metrics.width.toFixed(2)),
    hash: hash >>> 0,
  };
}

async function evaluateProbe(probe) {
  const face = [...document.fonts].find(
    (candidate) => normalizeFamily(candidate.family) === probe.family
  );
  let loaded = false;

  if (face) {
    try {
      await face.load();
      loaded = face.status === "loaded";
    } catch {
      loaded = false;
    }
  }

  await document.fonts.ready;

  const fontCheck = document.fonts.check(`48px "${probe.family}"`, SAMPLE_TEXT);
  const candidate = renderSignature(probe.family);
  const fallback = renderSignature("monospace");
  const differsFromFallback =
    candidate.hash !== fallback.hash ||
    Math.abs(candidate.width - fallback.width) > 0.1;

  return {
    ...probe,
    pass: loaded && fontCheck && differsFromFallback,
    loaded,
    fontCheck,
    candidate,
    fallback,
  };
}

function renderResult(result) {
  const container = document.querySelector(`[data-probe="${result.id}"]`);
  const status = container.querySelector("[data-status]");
  const detail = container.querySelector("[data-detail]");

  status.textContent = result.pass ? "PASS" : "FAIL";
  status.dataset.status = result.pass ? "pass" : "fail";
  if (Object.hasOwn(result, "error")) {
    detail.textContent = `error=${result.error}`;
    return;
  }
  detail.textContent =
    `loaded=${result.loaded}; check=${result.fontCheck}; ` +
    `width=${result.candidate.width}; fallback=${result.fallback.width}`;
}

async function run() {
  document.querySelector("#environment").textContent = navigator.userAgent;
  const results = [];

  for (const probe of PROBES) {
    let result;
    try {
      result = await evaluateProbe(probe);
      renderResult(result);
    } catch (error) {
      result = { ...probe, pass: false, error: errorMessage(error) };
      try {
        renderResult(result);
      } catch {
        // The summary still records the failure if this probe's DOM is unavailable.
      }
    }
    results.push(result);
  }

  document.querySelector("#result-summary").textContent = [
    navigator.userAgent,
    ...results.map(
      (result) =>
        Object.hasOwn(result, "error")
          ? `${result.localName}: FAIL (error=${result.error})`
          : `${result.localName}: ${result.pass ? "PASS" : "FAIL"} ` +
            `(loaded=${result.loaded}, check=${result.fontCheck}, ` +
            `width=${result.candidate.width}, fallback=${result.fallback.width})`
    ),
  ].join("\n");
}

run().catch((error) => {
  const summary = document.querySelector("#result-summary");
  if (summary) {
    summary.textContent = `字体探针失败: ${errorMessage(error)}`;
  }
});
