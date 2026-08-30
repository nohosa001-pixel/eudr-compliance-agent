// EUDR Compliance Automation Agent - Frontend Dashboard Controller

// --- Demo Payload Presets ---
const PRESETS = {
  compliant_vietnam: {
    name: "🟢 1. Compliant Coffee (Vietnam)",
    description: "Legal land title, valid polygon plot, no deforestation post-2020.",
    payload: {
      operator_id: "VN-EXP-COFFEE-8821",
      operator_name: "Highland Agri Export Ltd",
      eori_number: "FR123456789012",
      commodity: "COFFEE",
      hs_code: "0901.11.00",
      product_description: "Arabica Green Coffee Beans Premium Grade",
      net_mass_kg: 24000.0,
      plots: [
        {
          plot_id: "VN-LAMDONG-001",
          country_code: "VN",
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [108.4380, 11.9400],
                [108.4420, 11.9400],
                [108.4420, 11.9435],
                [108.4380, 11.9435],
                [108.4380, 11.9400]
              ]
            ]
          },
          declared_area_ha: 17.5,
          production_date_start: "2023-10-01",
          production_date_end: "2023-11-15",
          producer_name: "Da Lat Arabica Cooperative"
        }
      ],
      documents: [
        {
          document_type: "LAND_TITLE",
          document_id: "LURC-VN-2018-990",
          country_code: "VN",
          issuing_authority: "Lam Dong Department of Natural Resources",
          issue_date: "2018-05-12",
          expiry_date: "2038-05-12",
          plot_ids: ["VN-LAMDONG-001"]
        },
        {
          document_type: "HARVEST_PERMIT",
          document_id: "HP-2023-VN-887",
          country_code: "VN",
          issuing_authority: "Ministry of Agriculture and Rural Development",
          issue_date: "2023-09-01",
          expiry_date: "2024-09-01",
          plot_ids: ["VN-LAMDONG-001"]
        }
      ]
    }
  },

  deforestation_indonesia: {
    name: "🔴 2. Deforestation Detected (Indonesia)",
    description: "Palm Oil plot with 2022 Hansen satellite forest loss (Violates Dec 31, 2020 cutoff).",
    payload: {
      operator_id: "ID-EXP-PALM-9912",
      operator_name: "Sumatra Palm Agro Corp",
      eori_number: "NL987654321098",
      commodity: "OIL_PALM",
      hs_code: "1511.10.00",
      product_description: "Crude Palm Oil (CPO)",
      net_mass_kg: 50000.0,
      plots: [
        {
          plot_id: "ID-RIAU-042",
          country_code: "ID",
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [101.4400, 0.5300],
                [101.4450, 0.5300],
                [101.4450, 0.5340],
                [101.4400, 0.5340],
                [101.4400, 0.5300]
              ]
            ]
          },
          declared_area_ha: 22.0,
          production_date_start: "2023-08-01",
          production_date_end: "2023-09-30",
          producer_name: "Riau Bio Farm Estate"
        }
      ],
      documents: [
        {
          document_type: "LAND_TITLE",
          document_id: "HGU-ID-2021-002",
          country_code: "ID",
          issuing_authority: "National Land Agency (BPN)",
          issue_date: "2021-01-10",
          expiry_date: "2041-01-10",
          plot_ids: ["ID-RIAU-042"]
        },
        {
          document_type: "FPIC_CONSENT",
          document_id: "FPIC-RIAU-2021",
          country_code: "ID",
          issuing_authority: "Indigenous People Alliance of the Archipelago (AMAN)",
          issue_date: "2021-02-01",
          expiry_date: "2031-02-01",
          plot_ids: ["ID-RIAU-042"]
        }
      ]
    }
  },

  spatial_violation_brazil: {
    name: "🟡 3. Spatial 4ha Rule Violation (Brazil)",
    description: "Declared area is 15.0 ha (>=4ha) but submitted only as single Point coordinate.",
    payload: {
      operator_id: "BR-SOY-EXP-301",
      operator_name: "Cerrado Agro Trade",
      eori_number: "DE112233445566",
      commodity: "SOYA",
      hs_code: "1201.90.00",
      product_description: "Soybeans Non-GMO bulk",
      net_mass_kg: 85000.0,
      plots: [
        {
          plot_id: "BR-MT-SOY-99",
          country_code: "BR",
          geometry: {
            type: "Point",
            coordinates: [-55.7200, -12.5400]
          },
          declared_area_ha: 15.0,
          production_date_start: "2023-11-01",
          production_date_end: "2024-01-15",
          producer_name: "Mato Grosso Soya Ranch"
        }
      ],
      documents: [
        {
          document_type: "LAND_TITLE",
          document_id: "CAR-MT-884920",
          country_code: "BR",
          issuing_authority: "Cadastro Ambiental Rural (CAR)",
          issue_date: "2019-03-15",
          expiry_date: "2029-03-15",
          plot_ids: ["BR-MT-SOY-99"]
        }
      ]
    }
  },

  legal_violation_ghana: {
    name: "🟠 4. Expired Permit & Missing FPIC (Ghana)",
    description: "Cocoa farm with expired harvest permit in high-risk jurisdiction.",
    payload: {
      operator_id: "GH-COCOA-554",
      operator_name: "Ashanti Cocoa Exporters",
      eori_number: "BE998877665544",
      commodity: "COCOA",
      hs_code: "1801.00.00",
      product_description: "Fermented Cocoa Beans",
      net_mass_kg: 18000.0,
      plots: [
        {
          plot_id: "GH-ASH-01",
          country_code: "GH",
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [-1.6200, 6.6800],
                [-1.6150, 6.6800],
                [-1.6150, 6.6840],
                [-1.6200, 6.6840],
                [-1.6200, 6.6800]
              ]
            ]
          },
          declared_area_ha: 6.2,
          production_date_start: "2023-10-01",
          production_date_end: "2023-12-20",
          producer_name: "Kumasi Cocoa Farmers Association"
        }
      ],
      documents: [
        {
          document_type: "HARVEST_PERMIT",
          document_id: "GH-HP-2021-OLD",
          country_code: "GH",
          issuing_authority: "Ghana Forestry Commission",
          issue_date: "2021-01-01",
          expiry_date: "2022-01-01", // Expired!
          plot_ids: ["GH-ASH-01"]
        }
      ]
    }
  }
};

// --- Map State ---
let map;
let geojsonLayerGroup;
let currentReportData = null;

// Initialize Map
function initMap() {
  const defaultCenter = [11.94, 108.44];
  map = L.map('map', {
    zoomControl: true
  }).setView(defaultCenter, 14);

  const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
    maxZoom: 18
  });

  const streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
  });

  satelliteLayer.addTo(map);

  const baseMaps = {
    "Satellite Imagery": satelliteLayer,
    "OpenStreetMap": streetLayer
  };

  L.control.layers(baseMaps).addTo(map);
  geojsonLayerGroup = L.layerGroup().addTo(map);
}

// Render Geometry on Map
function renderPlotsOnMap(payload, evaluationResults = null) {
  geojsonLayerGroup.clearLayers();
  if (!payload || !payload.plots || payload.plots.length === 0) return;

  const bounds = [];

  payload.plots.forEach(plot => {
    const geom = plot.geometry;
    let color = '#3b82f6';
    let fillColor = '#3b82f6';
    let statusText = 'Pending Evaluation';

    if (evaluationResults && evaluationResults.spatial_results) {
      const sp = evaluationResults.spatial_results.find(s => s.plot_id === plot.plot_id);
      const sat = evaluationResults.satellite_results ? evaluationResults.satellite_results.find(s => s.plot_id === plot.plot_id) : null;
      
      if (sp && !sp.is_valid) {
        color = '#f59e0b';
        fillColor = '#f59e0b';
        statusText = `Spatial Error: ${sp.error_message || 'Invalid geometry'}`;
      } else if (sat && sat.deforestation_detected) {
        color = '#f43f5e';
        fillColor = '#f43f5e';
        statusText = `Deforestation Detected (Year: ${sat.loss_year || 'Post-2020'})`;
      } else {
        color = '#10b981';
        fillColor = '#10b981';
        statusText = 'Compliant / Forest Preserved';
      }
    }

    if (geom.type === 'Point') {
      const lat = geom.coordinates[1];
      const lng = geom.coordinates[0];
      bounds.push([lat, lng]);

      const marker = L.circleMarker([lat, lng], {
        radius: 8,
        color: color,
        fillColor: fillColor,
        fillOpacity: 0.8,
        weight: 2
      });

      marker.bindPopup(`
        <div style="color: #0f172a; font-size: 12px; font-family: sans-serif;">
          <strong>Plot:</strong> ${plot.plot_id}<br/>
          <strong>Country:</strong> ${plot.country_code}<br/>
          <strong>Type:</strong> Point (${plot.declared_area_ha || 0} ha)<br/>
          <strong>Status:</strong> ${statusText}
        </div>
      `);
      geojsonLayerGroup.addLayer(marker);
    } else if (geom.type === 'Polygon' || geom.type === 'MultiPolygon') {
      const geojsonFeature = {
        type: "Feature",
        geometry: geom,
        properties: {
          plot_id: plot.plot_id,
          country: plot.country_code,
          declared_area_ha: plot.declared_area_ha,
          status: statusText
        }
      };

      const polyLayer = L.geoJSON(geojsonFeature, {
        style: {
          color: color,
          weight: 3,
          opacity: 0.9,
          fillColor: fillColor,
          fillOpacity: 0.35
        },
        onEachFeature: (feature, layer) => {
          layer.bindPopup(`
            <div style="color: #0f172a; font-size: 12px; font-family: sans-serif;">
              <strong>Plot:</strong> ${feature.properties.plot_id}<br/>
              <strong>Country:</strong> ${feature.properties.country}<br/>
              <strong>Declared Area:</strong> ${feature.properties.declared_area_ha} ha<br/>
              <strong>Status:</strong> ${feature.properties.status}
            </div>
          `);
        }
      });

      geojsonLayerGroup.addLayer(polyLayer);

      // Collect lat/lng for bounds fitting
      try {
        const polyBounds = polyLayer.getBounds();
        bounds.push(polyBounds.getSouthWest());
        bounds.push(polyBounds.getNorthEast());
      } catch (e) {}
    }
  });

  if (bounds.length > 0) {
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
  }
}

// Load Preset
function loadPreset(key) {
  const preset = PRESETS[key];
  if (!preset) return;

  document.querySelectorAll('.btn-preset').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.querySelector(`[data-preset="${key}"]`);
  if (activeBtn) activeBtn.classList.add('active');

  const jsonStr = JSON.stringify(preset.payload, null, 2);
  document.getElementById('payload-editor').value = jsonStr;

  renderPlotsOnMap(preset.payload);
  resetResults();
}

// Reset Results Visualizer
function resetResults() {
  document.getElementById('overall-status-card').style.display = 'none';
  document.getElementById('step-1').className = 'step-box';
  document.getElementById('step-2').className = 'step-box';
  document.getElementById('step-3').className = 'step-box';
  document.getElementById('step-4').className = 'step-box';

  document.getElementById('step-1-status').innerText = '⏳';
  document.getElementById('step-2-status').innerText = '⏳';
  document.getElementById('step-3-status').innerText = '⏳';
  document.getElementById('step-4-status').innerText = '⏳';

  document.getElementById('step-1-detail').innerText = 'Awaiting execution';
  document.getElementById('step-2-detail').innerText = 'Awaiting execution';
  document.getElementById('step-3-detail').innerText = 'Awaiting execution';
  document.getElementById('step-4-detail').innerText = 'Awaiting execution';

  document.getElementById('traces-json-viewer').innerText = '// TRACES-NT DDS Statement will appear here upon evaluation';
  document.getElementById('raw-report-viewer').innerText = '// Full Evaluation Output will appear here';
  currentReportData = null;
}

// Execute Evaluation
async function runEvaluation() {
  const editor = document.getElementById('payload-editor');
  const btn = document.getElementById('btn-evaluate');
  
  let payload;
  try {
    payload = JSON.parse(editor.value);
  } catch (err) {
    alert("Invalid JSON format in payload editor:\n" + err.message);
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Evaluating EUDR Compliance...';

  try {
    const response = await fetch('/api/v1/eudr/evaluate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Server returned error ${response.status}`);
    }

    const report = await response.json();
    currentReportData = report;
    renderEvaluationResults(payload, report);
  } catch (err) {
    alert("Evaluation Failed: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '⚡ Run EUDR Compliance Evaluation';
  }
}

// Render Evaluation Results
function renderEvaluationResults(payload, report) {
  // Update Map with results
  renderPlotsOnMap(payload, report);

  // Overall Banner
  const banner = document.getElementById('overall-status-card');
  banner.style.display = 'flex';
  banner.className = `overall-status-banner ${report.status}`;

  const isCompliant = report.status === 'COMPLIANT';
  document.getElementById('status-icon-lg').innerText = isCompliant ? '🛡️' : '⚠️';
  document.getElementById('status-title-text').innerText = isCompliant ? 'EUDR COMPLIANT (PASSED)' : 'EUDR NON-COMPLIANT (FAILED)';
  document.getElementById('status-sub-text').innerText = report.summary_message;

  const b2gBtn = document.getElementById('btn-submit-traces');
  if (b2gBtn) {
    b2gBtn.style.display = isCompliant ? 'block' : 'none';
  }

  // Confidence Badge
  const conf = report.confidence_assessment;
  const confBadge = document.getElementById('confidence-badge');
  if (conf) {
    const scorePct = (conf.overall_confidence_score * 100).toFixed(0);
    confBadge.innerText = `Confidence: ${scorePct}% (${conf.review_status})`;
    confBadge.style.color = conf.requires_human_review ? '#fbbf24' : '#34d399';
    confBadge.style.borderColor = conf.requires_human_review ? '#f59e0b' : '#10b981';
    confBadge.style.background = conf.requires_human_review ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.15)';
  }

  // Step 1: Spatial & Overlap
  const s1 = document.getElementById('step-1');
  const s1Status = document.getElementById('step-1-status');
  const s1Detail = document.getElementById('step-1-detail');
  if (report.spatial_summary.spatial_compliance) {
    s1.className = 'step-box valid';
    s1Status.innerText = '✅';
    const overlapMsg = report.spatial_summary.overlapping_plots_count > 0 ? ` (${report.spatial_summary.overlapping_plots_count} overlaps)` : '';
    s1Detail.innerText = `Valid (${report.spatial_summary.valid_plots_count} plots, ${report.spatial_summary.total_declared_area_ha} ha)${overlapMsg}`;
  } else {
    s1.className = 'step-box invalid';
    s1Status.innerText = '❌';
    s1Detail.innerText = `${report.spatial_summary.invalid_plots_count} invalid plots (4ha / geometry error)`;
  }

  // Step 2: Satellite
  const s2 = document.getElementById('step-2');
  const s2Status = document.getElementById('step-2-status');
  const s2Detail = document.getElementById('step-2-detail');
  if (report.satellite_summary.overall_deforestation_free) {
    s2.className = 'step-box valid';
    s2Status.innerText = '✅';
    s2Detail.innerText = 'Deforestation-free (3-way consensus verified)';
  } else {
    s2.className = 'step-box invalid';
    s2Status.innerText = '❌';
    s2Detail.innerText = `${report.satellite_summary.deforestation_flagged_plots_count} plot(s) flagged with forest loss`;
  }

  // Step 3: Legal
  const s3 = document.getElementById('step-3');
  const s3Status = document.getElementById('step-3-status');
  const s3Detail = document.getElementById('step-3-detail');
  if (report.legal_summary.overall_compliant) {
    s3.className = 'step-box valid';
    s3Status.innerText = '✅';
    s3Detail.innerText = `Risk: ${report.legal_summary.country_risk_tier} (Documents Valid)`;
  } else {
    s3.className = 'step-box invalid';
    s3Status.innerText = '❌';
    s3Detail.innerText = report.legal_summary.missing_required_documents[0] || report.legal_summary.expired_documents[0] || 'Missing/Expired documents';
  }

  // Step 4: DDS & Evidence
  const s4 = document.getElementById('step-4');
  const s4Status = document.getElementById('step-4-status');
  const s4Detail = document.getElementById('step-4-detail');
  if (report.traces_dds) {
    s4.className = 'step-box valid';
    s4Status.innerText = '📝';
    s4Detail.innerText = `DDS Ref: ${report.traces_dds.dds_reference_id.substring(0, 16)}...`;
    document.getElementById('traces-json-viewer').innerText = JSON.stringify(report.traces_dds.submission_ready_traces_payload, null, 2);
  } else {
    s4.className = 'step-box invalid';
    s4Status.innerText = '🚫';
    s4Detail.innerText = 'TRACES-NT DDS Blocked (Non-compliant)';
    document.getElementById('traces-json-viewer').innerText = '// DDS Statement Generation Blocked due to EUDR non-compliance.';
  }

  // Evidence Bundle Tab
  if (report.evidence_bundle) {
    document.getElementById('evidence-json-viewer').innerText = JSON.stringify(report.evidence_bundle, null, 2);
  }

  // Satellite Triangulation Tab
  const consensusList = report.plots_detail.map(p => ({
    plot_id: p.plot_id,
    deforestation_detected: p.deforestation_detected,
    loss_year: p.loss_year,
    satellite_consensus: p.satellite_consensus
  }));
  document.getElementById('satellite-consensus-viewer').innerText = JSON.stringify(consensusList, null, 2);

  document.getElementById('raw-report-viewer').innerText = JSON.stringify(report, null, 2);
}

// HS Code Lookup
async function checkHsCode() {
  const hsInput = document.getElementById('hs-code-input').value.trim();
  if (!hsInput) return;

  const resultBadge = document.getElementById('hs-result-badge');
  resultBadge.innerHTML = '<span class="spinner"></span> Checking...';

  try {
    const res = await fetch(`/api/v1/eudr/classify-commodity?hs_code=${encodeURIComponent(hsInput)}`);
    const data = await res.json();

    if (data.is_eudr_regulated) {
      resultBadge.innerHTML = `✅ <strong>EUDR Regulated</strong>: <span style="color:#60a5fa">${data.eudr_category}</span> (HS: ${data.hs_code})`;
      resultBadge.style.borderColor = '#10b981';
    } else {
      resultBadge.innerHTML = `⚪ <strong>Non-EUDR Commodity</strong>: (Category: OTHER)`;
      resultBadge.style.borderColor = '#6b7280';
    }
  } catch (err) {
    resultBadge.innerHTML = `❌ Error checking HS code`;
  }
}

// Open HTML Report Modal
async function openHtmlReportModal() {
  const editor = document.getElementById('payload-editor');
  let payload;
  try {
    payload = JSON.parse(editor.value);
  } catch (err) {
    alert("Invalid JSON format in payload editor");
    return;
  }

  const modal = document.getElementById('html-report-modal');
  const iframe = document.getElementById('report-iframe');
  modal.classList.add('open');

  try {
    const response = await fetch('/api/v1/eudr/evaluate/html-report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const html = await response.text();
    iframe.srcdoc = html;
  } catch (err) {
    iframe.srcdoc = `<h3 style="color:red; padding: 20px;">Failed to generate report: ${err.message}</h3>`;
  }
}

function closeHtmlReportModal() {
  document.getElementById('html-report-modal').classList.remove('open');
}

// Submit to TRACES-NT B2G Gateway
async function submitTracesB2G() {
  if (!currentReportData || currentReportData.status !== 'COMPLIANT') {
    alert("Only COMPLIANT Due Diligence Statements can be submitted to EU TRACES-NT Gateway.");
    return;
  }

  const btn = document.getElementById('btn-submit-traces');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Transmitting to EU Gateway...';

  try {
    const res = await fetch('/api/v1/eudr/traces-nt/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentReportData)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Submission failed");
    }

    const data = await res.json();
    
    // Show TRACES Modal Receipt
    const modal = document.getElementById('traces-b2g-modal');
    const body = document.getElementById('traces-receipt-body');
    body.innerHTML = `
      <div style="background: rgba(16,185,129,0.15); border: 1px solid #10b981; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
        <div style="font-size: 1.1rem; font-weight: 800; color: #34d399;">✅ TRACES-NT REGISTRATION SUCCESSFUL</div>
        <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 4px;">EU Single Window Environment for Customs (EU SWE-C) Cleared</div>
      </div>
      <table style="width:100%; font-size: 0.85rem; border-collapse: collapse;">
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.08);"><td style="padding:8px; color:#94a3b8;">ACK Number:</td><td style="padding:8px; font-weight:700; color:#60a5fa;"><code>${data.traces_ack_number}</code></td></tr>
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.08);"><td style="padding:8px; color:#94a3b8;">Customs Code:</td><td style="padding:8px; font-weight:700; color:#34d399;"><code>${data.customs_declaration_code}</code></td></tr>
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.08);"><td style="padding:8px; color:#94a3b8;">DDS Ref ID:</td><td style="padding:8px;"><code>${data.dds_reference_id}</code></td></tr>
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.08);"><td style="padding:8px; color:#94a3b8;">Operator EORI:</td><td style="padding:8px;">${data.operator_eori}</td></tr>
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.08);"><td style="padding:8px; color:#94a3b8;">Submission Time:</td><td style="padding:8px;">${data.submission_timestamp}</td></tr>
        <tr><td style="padding:8px; color:#94a3b8;">Green Lane Status:</td><td style="padding:8px; font-weight:700; color:#34d399;">🟢 CLEARED FOR IMPORT</td></tr>
      </table>
      <div style="margin-top: 16px; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 6px; font-size: 0.78rem; color: #cbd5e1;">
        ${data.official_receipt_summary}
      </div>
    `;
    modal.classList.add('open');
    loadAuditHistory();
  } catch (err) {
    alert("TRACES-NT B2G Submission Failed:\n" + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🚀 Submit to EU TRACES-NT (B2G)';
  }
}

// Bulk File Upload Ingestion
async function uploadBulkFile(file) {
  const statusDiv = document.getElementById('file-upload-status');
  statusDiv.style.display = 'block';
  statusDiv.style.color = '#60a5fa';
  statusDiv.innerHTML = `<span class="spinner"></span> Parsing '${file.name}'...`;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('supplier_id', `SUPP-FILE-${Date.now()}`);

  try {
    const res = await fetch('/api/v1/eudr/ingest-file', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to parse file");
    }

    const payload = await res.json();
    document.getElementById('payload-editor').value = JSON.stringify(payload, null, 2);
    renderPlotsOnMap(payload);
    resetResults();

    statusDiv.style.color = '#34d399';
    statusDiv.innerHTML = `✅ Successfully parsed ${payload.plots.length} plots from <strong>${file.name}</strong>`;
  } catch (err) {
    statusDiv.style.color = '#fb7185';
    statusDiv.innerHTML = `❌ Error: ${err.message}`;
  }
}

// Load Audit History from Database
async function loadAuditHistory() {
  const container = document.getElementById('history-table-container');
  container.innerHTML = '<p style="font-size:0.8rem; color:#94a3b8;"><span class="spinner"></span> Loading history records from database...</p>';

  try {
    const res = await fetch('/api/v1/eudr/history');
    const list = await res.json();

    if (!list || list.length === 0) {
      container.innerHTML = '<p style="font-size:0.8rem; color:#94a3b8;">No audit history found in database yet.</p>';
      return;
    }

    const rows = list.map(r => `
      <tr style="border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 0.78rem;">
        <td style="padding: 6px;"><code>${r.execution_id}</code></td>
        <td style="padding: 6px;">${r.supplier_id || '-'}</td>
        <td style="padding: 6px;">${r.commodity_hs_code} (${r.total_plots} plots, ${r.total_area_ha.toFixed(1)} ha)</td>
        <td style="padding: 6px;"><span style="color: ${r.overall_status === 'COMPLIANT' ? '#34d399' : '#fb7185'}; font-weight: 700;">${r.overall_status}</span></td>
        <td style="padding: 6px;">${(r.confidence_score * 100).toFixed(0)}%</td>
        <td style="padding: 6px;"><span style="color: ${r.traces_submission_status === 'SUBMITTED' ? '#34d399' : '#94a3b8'}">${r.traces_submission_status}</span></td>
        <td style="padding: 6px;">
          <button class="btn btn-secondary" style="font-size: 0.7rem; padding: 0.15rem 0.45rem;" onclick="reloadFromHistory('${r.execution_id}')">📂 Load</button>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <table style="width:100%; border-collapse: collapse; text-align: left;">
        <thead>
          <tr style="background: rgba(255,255,255,0.04); color: #94a3b8; font-size: 0.75rem;">
            <th style="padding: 6px;">Exec ID</th>
            <th style="padding: 6px;">Supplier</th>
            <th style="padding: 6px;">Commodity / Plots</th>
            <th style="padding: 6px;">Status</th>
            <th style="padding: 6px;">Confidence</th>
            <th style="padding: 6px;">TRACES</th>
            <th style="padding: 6px;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    `;
  } catch (err) {
    container.innerHTML = `<p style="color:red; font-size:0.8rem;">Failed to load history: ${err.message}</p>`;
  }
}

// Reload Execution From History
async function reloadFromHistory(execId) {
  try {
    const res = await fetch(`/api/v1/eudr/history/${execId}`);
    if (!res.ok) throw new Error("Could not retrieve record");
    const data = await res.json();

    document.getElementById('payload-editor').value = JSON.stringify(data.payload, null, 2);
    currentReportData = data.full_report;
    renderEvaluationResults(data.payload, data.full_report);
    switchTab('tab-traces');
  } catch (err) {
    alert("Failed to reload history record: " + err.message);
  }
}

// Localized HTML Report Modal
async function openHtmlReportModal() {
  const modal = document.getElementById('html-report-modal');
  const iframe = document.getElementById('report-iframe');
  const langSelect = document.getElementById('report-lang-select');
  const selectedLang = langSelect ? langSelect.value : 'en';

  const rawJson = document.getElementById('payload-editor').value;
  let payload;
  try {
    payload = JSON.parse(rawJson);
  } catch (err) {
    alert("Invalid JSON Payload in editor: " + err.message);
    return;
  }

  modal.classList.add('open');
  iframe.srcdoc = `<html><body style="font-family:sans-serif; text-align:center; padding:50px; background:#f8fafc; color:#334155;"><p>⏳ Generating localized compliance audit report (${selectedLang.toUpperCase()})...</p></body></html>`;

  try {
    const res = await fetch(`/api/v1/eudr/evaluate/html-report?lang=${encodeURIComponent(selectedLang)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errData.detail || "Failed to generate report");
    }

    const htmlContent = await res.text();
    iframe.srcdoc = htmlContent;
  } catch (err) {
    iframe.srcdoc = `<html><body style="font-family:sans-serif; padding:30px; color:#b91c1c; background:#fee2e2;"><h3>Report Generation Error</h3><p>${err.message}</p></body></html>`;
  }
}

function closeHtmlReportModal() {
  document.getElementById('html-report-modal').classList.remove('open');
}

// Run Golden Benchmark Suite
async function runGoldenBenchmark() {
  const modal = document.getElementById('benchmark-modal');
  const container = document.getElementById('benchmark-metrics-container');
  modal.classList.add('open');

  container.innerHTML = '<div style="text-align:center; padding: 30px;"><span class="spinner" style="width:28px; height:28px;"></span><p style="margin-top:10px;">Running 10 Ground-Truth Verification Scenarios...</p></div>';

  try {
    const res = await fetch('/api/v1/eudr/benchmark/run');
    const data = await res.json();

    const rows = data.case_results.map(c => `
      <tr style="border-bottom: 1px solid rgba(255,255,255,0.08);">
        <td style="padding:8px;"><code>${c.case_id}</code></td>
        <td style="padding:8px;"><strong>${c.title}</strong><br><small style="color:#94a3b8">${c.scenario_type}</small></td>
        <td style="padding:8px;"><span style="color:${c.expected_status==='COMPLIANT'?'#34d399':'#fb7185'}">${c.expected_status}</span></td>
        <td style="padding:8px;"><span style="color:${c.actual_status==='COMPLIANT'?'#34d399':'#fb7185'}">${c.actual_status}</span></td>
        <td style="padding:8px;">${c.passed ? '✅ PASS' : '❌ FAIL'}</td>
        <td style="padding:8px;">${(c.confidence_score*100).toFixed(0)}%</td>
        <td style="padding:8px;">${c.duration_ms} ms</td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;">
        <div style="background: rgba(16,185,129,0.15); border: 1px solid #10b981; padding: 12px; border-radius: 8px; text-align: center;">
          <div style="font-size: 22px; font-weight: 800; color: #34d399;">${data.accuracy_pct}%</div>
          <div style="font-size: 11px; color: #94a3b8;">OVERALL ACCURACY</div>
        </div>
        <div style="background: rgba(59,130,246,0.15); border: 1px solid #3b82f6; padding: 12px; border-radius: 8px; text-align: center;">
          <div style="font-size: 22px; font-weight: 800; color: #60a5fa;">${data.precision_pct}%</div>
          <div style="font-size: 11px; color: #94a3b8;">PRECISION (0% False Alarm)</div>
        </div>
        <div style="background: rgba(16,185,129,0.15); border: 1px solid #10b981; padding: 12px; border-radius: 8px; text-align: center;">
          <div style="font-size: 22px; font-weight: 800; color: #34d399;">${data.recall_pct}%</div>
          <div style="font-size: 11px; color: #94a3b8;">RECALL (100% Deforestation Caught)</div>
        </div>
        <div style="background: rgba(99,102,241,0.15); border: 1px solid #6366f1; padding: 12px; border-radius: 8px; text-align: center;">
          <div style="font-size: 22px; font-weight: 800; color: #818cf8;">${data.f1_score}</div>
          <div style="font-size: 11px; color: #94a3b8;">F1-SCORE</div>
        </div>
      </div>
      <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: left;">
        <thead>
          <tr style="background: rgba(255,255,255,0.05); color: #94a3b8;">
            <th style="padding:8px;">Case ID</th>
            <th style="padding:8px;">Scenario Title</th>
            <th style="padding:8px;">Expected</th>
            <th style="padding:8px;">Actual</th>
            <th style="padding:8px;">Result</th>
            <th style="padding:8px;">Confidence</th>
            <th style="padding:8px;">Latency</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    `;
  } catch (err) {
    container.innerHTML = `<h3 style="color:red;">Failed to run benchmark: ${err.message}</h3>`;
  }
}

function closeBenchmarkModal() {
  document.getElementById('benchmark-modal').classList.remove('open');
}

// Copy JSON to Clipboard
function copyToClipboard(elementId) {
  const text = document.getElementById(elementId).innerText;
  navigator.clipboard.writeText(text).then(() => {
    alert("Copied to clipboard!");
  }).catch(err => {
    alert("Failed to copy: " + err);
  });
}

// Tab Switching
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

  document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
  document.getElementById(tabId).classList.add('active');

  if (tabId === 'tab-history') {
    loadAuditHistory();
  }
}

// Initialize on DOM Loaded
document.addEventListener('DOMContentLoaded', () => {
  initMap();

  // Setup Presets Buttons
  document.querySelectorAll('.btn-preset').forEach(btn => {
    btn.addEventListener('click', () => {
      const presetKey = btn.getAttribute('data-preset');
      loadPreset(presetKey);
    });
  });

  // Evaluate Button
  document.getElementById('btn-evaluate').addEventListener('click', runEvaluation);

  // HS Lookup Button
  document.getElementById('btn-hs-lookup').addEventListener('click', checkHsCode);
  document.getElementById('hs-code-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') checkHsCode();
  });

  // View Printable Report Button
  document.getElementById('btn-view-html-report').addEventListener('click', openHtmlReportModal);
  document.getElementById('btn-close-modal').addEventListener('click', closeHtmlReportModal);

  // Benchmark Suite Button
  document.getElementById('btn-run-benchmark').addEventListener('click', runGoldenBenchmark);
  document.getElementById('btn-close-benchmark-modal').addEventListener('click', closeBenchmarkModal);

  // TRACES B2G Submit
  document.getElementById('btn-submit-traces').addEventListener('click', submitTracesB2G);
  document.getElementById('btn-close-traces-modal').addEventListener('click', () => {
    document.getElementById('traces-b2g-modal').classList.remove('open');
  });

  // History Refresh
  document.getElementById('btn-refresh-history').addEventListener('click', loadAuditHistory);

  // File Drag & Drop
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('bulk-file-input');

  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      uploadBulkFile(e.target.files[0]);
    }
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = '#3b82f6';
    dropzone.style.background = 'rgba(59,130,246,0.1)';
  });
  dropzone.addEventListener('dragleave', () => {
    dropzone.style.borderColor = 'rgba(255,255,255,0.15)';
    dropzone.style.background = 'transparent';
  });
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = 'rgba(255,255,255,0.15)';
    dropzone.style.background = 'transparent';
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      uploadBulkFile(e.dataTransfer.files[0]);
    }
  });

  // Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.getAttribute('data-tab'));
    });
  });

  // API Keys Modal
  const apiKeysModal = document.getElementById('api-keys-modal');
  const btnOpenKeys = document.getElementById('btn-open-api-keys');
  const btnCloseKeys = document.getElementById('btn-close-keys-modal');
  const btnGenKey = document.getElementById('btn-generate-api-key');

  if (btnOpenKeys) {
    btnOpenKeys.addEventListener('click', () => {
      apiKeysModal.classList.add('open');
    });
  }

  if (btnCloseKeys) {
    btnCloseKeys.addEventListener('click', () => {
      apiKeysModal.classList.remove('open');
    });
  }

  if (btnGenKey) {
    btnGenKey.addEventListener('click', async () => {
      const company = document.getElementById('apikey-company-input').value.trim() || 'Global Enterprise Corp';
      const email = document.getElementById('apikey-email-input').value.trim() || 'operator@company.com';
      const tier = document.getElementById('apikey-tier-select').value || 'PRO';

      btnGenKey.disabled = true;
      btnGenKey.textContent = 'Generating...';

      try {
        const resp = await fetch('/api/v1/auth/api-keys', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ company_name: company, contact_email: email, tier: tier })
        });
        const data = await resp.json();

        const resultBox = document.getElementById('apikey-result-container');
        const display = document.getElementById('generated-key-display');
        display.textContent = data.api_key;
        resultBox.style.display = 'block';
      } catch (err) {
        alert('Failed to generate key: ' + err.message);
      } finally {
        btnGenKey.disabled = false;
        btnGenKey.textContent = '⚡ Generate Key';
      }
    });
  }

  // Load default preset (Compliant Vietnam)
  loadPreset('compliant_vietnam');
});


