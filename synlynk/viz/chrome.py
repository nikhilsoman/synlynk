"""Shared browser chrome injected into Vizor pages."""
import json
def _live_js(port: int) -> str:
    from synlynk.local_http_auth import ensure_local_token

    token_js = json.dumps(ensure_local_token())
    return f"""
<script>
(function() {{
  const PORT = {port};
  window.VIZOR_TOKEN = {token_js};
  window.vizorAuthHeaders = function(extra) {{
    const headers = {{'X-Synlynk-Token': window.VIZOR_TOKEN || ''}};
    if (extra) {{
      Object.keys(extra).forEach(function(k) {{ headers[k] = extra[k]; }});
    }}
    return headers;
  }};
  let lastUpdated = null;

  async function checkManifest() {{
    try {{
      const r = await fetch('/manifest.json?_=' + Date.now(), {{ headers: window.vizorAuthHeaders() }});
      if (!r.ok) return;
      const m = await r.json();
      if (lastUpdated === null) {{
        lastUpdated = m.updated_at;
        return;
      }}
      if (m.updated_at !== lastUpdated) {{
        lastUpdated = m.updated_at;
        fireNotification(m.updated_at);
        showReloadBanner(m.updated_at);
      }}
    }} catch (e) {{}}
  }}

  function fireNotification(updatedAt) {{
    if (Notification.permission !== 'granted') return;
    new Notification('synlynk viz updated', {{
      body: `Workspace snapshot refreshed at ${{new Date(updatedAt).toLocaleTimeString()}}`,
      tag: 'vizor-refresh',
    }});
  }}

  function showReloadBanner(updatedAt) {{
    const existing = document.getElementById('vizor-reload-banner');
    if (existing) existing.remove();
    const banner = document.createElement('div');
    banner.id = 'vizor-reload-banner';
    banner.style.cssText = `position:fixed;top:0;left:0;right:0;z-index:9999;background:#0d9e87;color:#fff;font-family:SF Mono,monospace;font-size:12px;padding:8px 16px;display:flex;align-items:center;gap:12px;`;
    banner.innerHTML = `<span>✦ Vizor updated at ${{new Date(updatedAt).toLocaleTimeString()}}</span>
      <button onclick="location.reload()" style="background:rgba(255,255,255,0.2);border:none;color:#fff;padding:3px 10px;border-radius:4px;cursor:pointer">↺ Reload</button>
      <button onclick="this.parentElement.remove()" style="background:none;border:none;color:#fff;cursor:pointer;margin-left:auto;font-size:16px">✕</button>`;
    document.body.prepend(banner);
  }}

  document.addEventListener('click', function requestOnce() {{
    if (Notification.permission === 'default') Notification.requestPermission();
    document.removeEventListener('click', requestOnce);
  }}, {{ once: true }});

  setInterval(checkManifest, 60000);
  checkManifest();
}})();
</script>
""".replace("\n", " ")

