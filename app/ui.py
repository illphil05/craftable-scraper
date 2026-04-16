"""Inline HTML for the password-gated scraper UI."""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Craftable Scraper</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 min-h-screen flex items-center justify-center">
<div class="bg-white rounded-2xl shadow-lg max-w-sm w-full mx-4 p-8">
  <div class="text-center mb-6">
    <div class="inline-flex items-center justify-center w-12 h-12 bg-blue-100 rounded-xl mb-3">
      <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
    </div>
    <h1 class="text-xl font-bold text-slate-900">Craftable Scraper</h1>
    <p class="text-sm text-slate-500 mt-1">Enter password to access the scraper UI</p>
  </div>
  __ERROR__
  <form method="POST" action="/login" class="space-y-3">
    <input type="password" name="password" placeholder="Password" required autofocus
      class="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
    <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition">
      Sign in
    </button>
  </form>
</div>
</body>
</html>"""

ERROR_BANNER = (
    '<div class="mb-4 px-3 py-2 rounded-lg text-sm bg-red-50 text-red-700 '
    'border border-red-200">Incorrect password</div>'
)


def login_page(error: bool = False) -> str:
    return LOGIN_HTML.replace("__ERROR__", ERROR_BANNER if error else "")


SCRAPER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Craftable Scraper</title>
<script src="https://cdn.tailwindcss.com"></script>
<script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body class="bg-slate-50 min-h-screen" x-data="scraperApp()">

<header class="bg-white border-b border-slate-200">
  <div class="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 bg-blue-100 rounded-lg flex items-center justify-center">
        <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/></svg>
      </div>
      <div>
        <h1 class="font-bold text-slate-900">Craftable Scraper</h1>
        <p class="text-xs text-slate-500">scraper.myrtle.cloud</p>
      </div>
    </div>
    <div class="flex items-center gap-3 text-sm">
      <a href="/docs" target="_blank" class="text-slate-600 hover:text-slate-900">API Docs</a>
      <a href="/health" target="_blank" class="text-slate-600 hover:text-slate-900">Health</a>
      <form method="POST" action="/logout"><button class="text-slate-600 hover:text-slate-900">Sign out</button></form>
    </div>
  </div>
</header>

<main class="max-w-5xl mx-auto px-6 py-8 space-y-6">

  <!-- Scrape form -->
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
    <h2 class="text-lg font-bold text-slate-900 mb-1">Scrape a careers page</h2>
    <p class="text-sm text-slate-500 mb-4">Paste any ATS URL — Greenhouse, Lever, Paylocity, iCIMS, Workday, or generic.</p>

    <div class="space-y-3">
      <div>
        <label class="text-sm font-medium text-slate-700">URL *</label>
        <input x-model="url" type="text" placeholder="https://boards.greenhouse.io/embed/job_board?for=stripe"
          class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          @keydown.enter="scrape()">
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="text-sm font-medium text-slate-700">Company name (optional)</label>
          <input x-model="companyName" type="text" placeholder="Auto-detected"
            class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="text-sm font-medium text-slate-700">Timeout (ms)</label>
          <input x-model.number="timeout" type="number" step="1000"
            class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
      </div>
      <label class="flex items-center gap-2 text-sm text-slate-700">
        <input x-model="debug" type="checkbox" class="rounded border-slate-300">
        Debug mode (returns HTML sample)
      </label>
    </div>

    <div class="mt-4 flex items-center gap-3">
      <button @click="scrape()" :disabled="loading || !url"
        class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-5 py-2 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed">
        <span x-show="!loading">Scrape</span>
        <span x-show="loading">Scraping…</span>
      </button>
      <button @click="clearAll()" class="text-sm text-slate-600 hover:text-slate-900">Clear</button>
      <span x-show="result" class="text-xs text-slate-500" x-text="`Method: ${result?.method} · ${result?.elapsed_ms}ms · ${result?.jobs_count} jobs`"></span>
    </div>

    <div x-show="error" class="mt-4 px-3 py-2 rounded-lg text-sm bg-red-50 text-red-700 border border-red-200" x-text="error"></div>
  </div>

  <!-- Results -->
  <div x-show="result && result.jobs.length > 0" class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-bold text-slate-900">Results <span class="text-slate-400 font-normal" x-text="`(${result?.jobs?.length})`"></span></h2>
      <button @click="copyJSON()" class="text-xs text-slate-600 hover:text-slate-900 border border-slate-200 px-3 py-1 rounded-lg">Copy JSON</button>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-slate-500 border-b border-slate-200">
            <th class="font-medium py-2 pr-4">Title</th>
            <th class="font-medium py-2 pr-4">Location</th>
            <th class="font-medium py-2">Link</th>
          </tr>
        </thead>
        <tbody>
          <template x-for="(job, i) in result.jobs" :key="i">
            <tr class="border-b border-slate-100 hover:bg-slate-50">
              <td class="py-2 pr-4 text-slate-900" x-text="job.title"></td>
              <td class="py-2 pr-4 text-slate-600" x-text="job.location || '—'"></td>
              <td class="py-2"><a x-show="job.url" :href="job.url" target="_blank" class="text-blue-600 hover:underline">Open →</a></td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>

  <div x-show="result && result.jobs.length === 0 && !error" class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 text-center text-slate-500 text-sm">
    No jobs found. Try debug mode to inspect the page HTML.
  </div>

  <!-- Debug HTML -->
  <div x-show="result?.html_sample" class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
    <h2 class="text-sm font-bold text-slate-900 mb-2">HTML sample <span class="text-slate-400 font-normal" x-text="`(${result?.html_size?.toLocaleString()} bytes total)`"></span></h2>
    <pre class="text-xs bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-x-auto max-h-96 overflow-y-auto" x-text="result?.html_sample"></pre>
  </div>

  <!-- History -->
  <div x-show="history.length > 0" class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-sm font-bold text-slate-900">Recent scrapes</h2>
      <button @click="clearHistory()" class="text-xs text-slate-500 hover:text-slate-900">Clear</button>
    </div>
    <div class="space-y-2">
      <template x-for="(h, i) in history" :key="i">
        <button @click="loadHistory(h)" class="w-full text-left flex items-center justify-between gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 border border-slate-100">
          <div class="min-w-0 flex-1">
            <div class="text-sm text-slate-900 truncate" x-text="h.url"></div>
            <div class="text-xs text-slate-500" x-text="`${h.method} · ${h.jobs_count} jobs · ${h.elapsed_ms}ms`"></div>
          </div>
          <span class="text-xs text-slate-400" x-text="new Date(h.at).toLocaleTimeString()"></span>
        </button>
      </template>
    </div>
  </div>

</main>

<script>
function scraperApp() {
  return {
    url: '',
    companyName: '',
    timeout: 30000,
    debug: false,
    loading: false,
    result: null,
    error: '',
    history: JSON.parse(localStorage.getItem('scraper_history') || '[]'),

    async scrape() {
      this.error = '';
      this.result = null;
      this.loading = true;
      let url = this.url.trim();
      if (!url.startsWith('http')) url = 'https://' + url;
      try {
        const r = await fetch('/scrape', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url,
            company_name: this.companyName || undefined,
            timeout: this.timeout,
            debug: this.debug,
          }),
        });
        const d = await r.json();
        if (!r.ok) {
          this.error = d.detail || `HTTP ${r.status}`;
        } else {
          this.result = d;
          this.history.unshift({
            url, method: d.method, jobs_count: d.jobs_count,
            elapsed_ms: d.elapsed_ms, at: Date.now(),
          });
          this.history = this.history.slice(0, 10);
          localStorage.setItem('scraper_history', JSON.stringify(this.history));
        }
      } catch (e) {
        this.error = 'Network error: ' + e.message;
      }
      this.loading = false;
    },

    clearAll() {
      this.url = '';
      this.companyName = '';
      this.result = null;
      this.error = '';
    },

    copyJSON() {
      navigator.clipboard.writeText(JSON.stringify(this.result, null, 2));
    },

    loadHistory(h) {
      this.url = h.url;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    clearHistory() {
      this.history = [];
      localStorage.removeItem('scraper_history');
    },
  };
}
</script>
</body>
</html>"""


def scraper_page() -> str:
    return SCRAPER_HTML
