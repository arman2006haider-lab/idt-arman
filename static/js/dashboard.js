(function () {
  var cfg = window.CROP_GUARD;
  if (!cfg) return;

  var POLL_INTERVAL_MS = 15000;
  var lastSevereCount = -1;

  function levelClass(level) {
    return ['safe', 'watch', 'alert', 'severe'].indexOf(level) >= 0 ? level : 'safe';
  }

  function riskLabel(level) {
    switch (level) {
      case 'watch': return cfg.translations.riskWatch;
      case 'alert': return cfg.translations.riskAlert;
      case 'severe': return cfg.translations.riskSevere;
      default: return cfg.translations.riskSafe;
    }
  }

  function updateGauge(risk) {
    var needle = document.getElementById('gauge-needle');
    var label = document.getElementById('gauge-level-name');
    if (!needle || !label) return;
    var pos = cfg.needlePos[risk];
    if (pos) {
      needle.setAttribute('x2', pos[0]);
      needle.setAttribute('y2', pos[1]);
    }
    label.textContent = riskLabel(risk);
    label.className = 'gauge-level-name ' + levelClass(risk);
  }

  function updateSensors(reading) {
    if (!reading) return;
    var soil = document.getElementById('val-soil');
    var rain = document.getElementById('val-rain');
    var temp = document.getElementById('val-temp');
    var hum = document.getElementById('val-humidity');
    var updated = document.getElementById('last-updated');

    if (soil) soil.textContent = reading.soil_moisture + cfg.translations.percent;
    if (rain) rain.textContent = reading.rain_intensity + ' ' + cfg.translations.mm + '/hr';
    if (temp) temp.textContent = reading.air_temperature + '\u00b0C';
    if (hum) hum.textContent = reading.air_humidity + cfg.translations.percent;
    if (updated) {
      updated.textContent = cfg.translations.lastUpdated + ': ' + reading.timestamp +
        ' UTC \u00b7 ' + (reading.device_id || '');
    }
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function updateAlerts(alerts) {
    var container = document.getElementById('alerts-list');
    if (!container) return;

    if (!alerts || alerts.length === 0) {
      container.innerHTML = '<div class="empty-state">' + escapeHtml(cfg.translations.noAlerts) + '</div>';
      return;
    }

    var sensorHazards = ['dry_soil', 'waterlogged_soil', 'flood'];
    var html = '';
    alerts.forEach(function (a) {
      var sourceLabel = sensorHazards.indexOf(a.hazard) >= 0
        ? cfg.translations.sourceSensor
        : cfg.translations.sourceForecast;
      html += '<div class="alert-item ' + a.level + '">' +
        '<div class="alert-title"><span>' + escapeHtml(a.title) + '</span>' +
        '<span class="level-pill ' + a.level + '">' + escapeHtml(riskLabel(a.level)) + '</span></div>' +
        '<div class="alert-meta">' + escapeHtml(sourceLabel) + '</div>' +
        '<div class="alert-message">' + escapeHtml(a.message) + '</div>' +
        '</div>';
    });
    container.innerHTML = html;
  }

  function playAlarm() {
    try {
      var AudioCtx = window.AudioContext || window.webkitAudioContext;
      var ctx = new AudioCtx();
      var now = ctx.currentTime;
      [0, 0.35, 0.7].forEach(function (offset) {
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.type = 'square';
        osc.frequency.value = 880;
        gain.gain.value = 0.15;
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + offset);
        osc.stop(now + offset + 0.25);
      });
    } catch (e) {
      // Web Audio not available; ignore.
    }
  }

  function refresh() {
    fetch('/api/farm/' + cfg.farmId + '/status')
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        updateGauge(data.risk);
        updateSensors(data.reading);
        updateAlerts(data.alerts);

        var severeCount = (data.alerts || []).filter(function (a) {
          return a.level === 'severe';
        }).length;

        var alarmToggle = document.getElementById('alarm-toggle');
        if (alarmToggle && alarmToggle.checked && severeCount > 0 && severeCount !== lastSevereCount) {
          playAlarm();
        }
        lastSevereCount = severeCount;
      })
      .catch(function () { /* network hiccup, ignore */ });
  }

  setInterval(refresh, POLL_INTERVAL_MS);
})();
