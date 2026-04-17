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
<script defer src="https://unpkg.com/alpinejs@3.14.8/dist/cdn.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  body { font-family: 'Inter', sans-serif; }
  [x-cloak] { display: none !important; }
  .slide-over-enter { transform: translateX(100%); }
  .slide-over-active { transform: translateX(0); transition: transform 0.2s ease-out; }
</style>
</head>
<body class="bg-slate-50 min-h-screen" x-data="app()" x-init="init()" x-cloak>

<!-- ═══ NAV ═══ -->
<nav class="sticky top-0 z-40 bg-white border-b border-slate-200">
  <div class="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
    <div class="flex items-center gap-6">
      <div class="flex items-center gap-2">
        <div class="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
          <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/></svg>
        </div>
        <span class="font-bold text-slate-900 text-sm">Craftable Scraper</span>
      </div>
      <div class="flex items-center gap-1">
        <button @click="navigate('overview')" :class="page==='overview' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'" class="px-3 py-1.5 rounded-lg text-sm font-medium transition">Overview</button>
        <button @click="navigate('jobs')" :class="page==='jobs' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'" class="px-3 py-1.5 rounded-lg text-sm font-medium transition">Jobs</button>
        <button @click="navigate('intelligence')" :class="page==='intelligence' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'" class="px-3 py-1.5 rounded-lg text-sm font-medium transition">Intelligence</button>
        <button @click="navigate('scrape')" :class="page==='scrape' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'" class="px-3 py-1.5 rounded-lg text-sm font-medium transition">Scrape</button>
      </div>
    </div>
    <div class="flex items-center gap-3 text-sm">
      <a href="/docs" target="_blank" class="text-slate-500 hover:text-slate-900">API</a>
      <form method="POST" action="/logout"><button class="text-slate-500 hover:text-slate-900">Sign out</button></form>
    </div>
  </div>
</nav>

<main class="max-w-7xl mx-auto px-6 py-6">

<!-- ═══════════════════════════════════════════════════ -->
<!-- PAGE 1: OVERVIEW                                    -->
<!-- ═══════════════════════════════════════════════════ -->
<div x-show="page==='overview'" x-cloak>

  <!-- Stat cards -->
  <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
    <div class="rounded-xl border border-slate-200 bg-white p-4">
      <div class="text-xs font-medium text-slate-500 mb-1">Companies</div>
      <div class="text-2xl font-bold text-slate-900" x-text="stats?.companies ?? '—'"></div>
    </div>
    <div class="rounded-xl border border-slate-200 bg-white p-4">
      <div class="text-xs font-medium text-slate-500 mb-1">Total Jobs</div>
      <div class="text-2xl font-bold text-slate-900" x-text="stats?.total_jobs ?? '—'"></div>
    </div>
    <div class="rounded-xl border border-slate-200 bg-white p-4">
      <div class="text-xs font-medium text-slate-500 mb-1">Active Jobs</div>
      <div class="text-2xl font-bold text-blue-600" x-text="stats?.active_jobs ?? '—'"></div>
    </div>
    <div class="rounded-xl border border-slate-200 bg-white p-4">
      <div class="text-xs font-medium text-slate-500 mb-1">Systems Detected</div>
      <div class="text-2xl font-bold text-slate-900" x-text="stats?.systems_detected ?? '—'"></div>
    </div>
    <div class="rounded-xl border border-slate-200 bg-white p-4">
      <div class="text-xs font-medium text-slate-500 mb-1">Scrapes (24h)</div>
      <div class="text-2xl font-bold text-slate-900" x-text="stats?.recent_scrapes_24h ?? '—'"></div>
    </div>
    <div class="rounded-xl border border-slate-200 bg-white p-4">
      <div class="text-xs font-medium text-slate-500 mb-1">Parsers</div>
      <div class="text-2xl font-bold text-slate-900" x-text="stats?.parsers_available ?? '8'"></div>
    </div>
  </div>

  <!-- Filters -->
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
    <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
      <h2 class="text-lg font-bold text-slate-900">Companies</h2>
      <div class="flex-1"></div>
      <input x-model.debounce.300ms="companiesSearch" @input="loadCompanies()" type="text" placeholder="Search companies..."
        class="w-full sm:w-64 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
      <select x-model="companiesRegion" @change="loadCompanies()" class="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="">All regions</option>
        <template x-for="r in regions" :key="r.region">
          <option :value="r.region" x-text="r.region + ' (' + r.count + ')'"></option>
        </template>
      </select>
    </div>

    <!-- Companies table -->
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-slate-500 bg-slate-50">
            <th class="font-medium py-2.5 px-3">Name</th>
            <th class="font-medium py-2.5 px-3">Region</th>
            <th class="font-medium py-2.5 px-3">Jobs</th>
            <th class="font-medium py-2.5 px-3">Systems</th>
            <th class="font-medium py-2.5 px-3">Last Scraped</th>
            <th class="font-medium py-2.5 px-3">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <template x-for="c in companies" :key="c.id">
            <tr class="hover:bg-slate-50">
              <td class="py-2.5 px-3">
                <button @click="navigate('company', c.id)" class="text-blue-600 hover:text-blue-800 font-medium" x-text="c.name"></button>
              </td>
              <td class="py-2.5 px-3">
                <span x-show="c.region" class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700" x-text="c.region"></span>
              </td>
              <td class="py-2.5 px-3 text-slate-600">
                <span class="text-blue-600 font-medium" x-text="c.jobs_count"></span>
                <span class="text-slate-400" x-text="'/' + c.total_jobs"></span>
              </td>
              <td class="py-2.5 px-3 text-slate-600" x-text="c.systems_count"></td>
              <td class="py-2.5 px-3 text-slate-500 text-xs" x-text="c.last_seen ? new Date(c.last_seen).toLocaleDateString() : '—'"></td>
              <td class="py-2.5 px-3">
                <button @click="rescrapeCompany(c)" class="text-slate-400 hover:text-blue-600" title="Re-scrape">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                </button>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div x-show="companies.length === 0 && !loading" class="py-8 text-center text-slate-400 text-sm">No companies found.</div>
    <div x-show="loading" class="py-8 text-center text-slate-400 text-sm">Loading...</div>

    <div class="flex items-center justify-between mt-4 pt-4 border-t border-slate-100" x-show="companiesTotal > 50">
      <span class="text-xs text-slate-500" x-text="'Showing ' + companies.length + ' of ' + companiesTotal"></span>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════ -->
<!-- PAGE 2: COMPANY DETAIL                              -->
<!-- ═══════════════════════════════════════════════════ -->
<div x-show="page==='company'" x-cloak>

  <!-- Back button -->
  <button @click="navigate('overview')" class="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 mb-4">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
    Back to overview
  </button>

  <!-- Header card -->
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6" x-show="company">
    <div class="flex items-start justify-between">
      <div>
        <h1 class="text-xl font-bold text-slate-900" x-text="company?.name"></h1>
        <div class="flex flex-wrap items-center gap-3 mt-2 text-sm text-slate-500">
          <a x-show="company?.website_url" :href="company?.website_url" target="_blank" class="text-blue-600 hover:underline flex items-center gap-1">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
            Website
          </a>
          <a x-show="company?.careers_url" :href="company?.careers_url" target="_blank" class="text-blue-600 hover:underline flex items-center gap-1">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
            Careers
          </a>
          <span x-show="company?.parent_company_name" class="text-slate-400" x-text="'Parent: ' + company?.parent_company_name"></span>
          <span x-show="company?.region" class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700" x-text="company?.region"></span>
        </div>
        <div class="flex gap-4 mt-2 text-xs text-slate-400">
          <span x-text="'First seen: ' + (company?.first_seen ? new Date(company.first_seen).toLocaleDateString() : '—')"></span>
          <span x-text="'Last seen: ' + (company?.last_seen ? new Date(company.last_seen).toLocaleDateString() : '—')"></span>
        </div>
      </div>
      <button @click="editModal = true" class="text-sm text-blue-600 hover:text-blue-800 font-medium border border-blue-200 px-3 py-1.5 rounded-lg">Edit</button>
    </div>
  </div>

  <!-- Edit modal -->
  <div x-show="editModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30" @click.self="editModal = false" x-cloak>
    <div class="bg-white rounded-2xl shadow-xl max-w-md w-full mx-4 p-6" @click.stop>
      <h2 class="text-lg font-bold text-slate-900 mb-4">Edit Company</h2>
      <div class="space-y-3">
        <div>
          <label class="text-sm font-medium text-slate-700">Name</label>
          <input x-model="editForm.name" type="text" class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="text-sm font-medium text-slate-700">Website URL</label>
          <input x-model="editForm.website_url" type="text" class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="text-sm font-medium text-slate-700">Careers URL</label>
          <input x-model="editForm.careers_url" type="text" class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="text-sm font-medium text-slate-700">Parent Company</label>
          <input x-model="editForm.parent_company_name" type="text" class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="text-sm font-medium text-slate-700">Region</label>
          <input x-model="editForm.region" type="text" class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
      </div>
      <div class="flex justify-end gap-2 mt-6">
        <button @click="editModal = false" class="text-sm text-slate-600 px-4 py-2 rounded-lg hover:bg-slate-50">Cancel</button>
        <button @click="saveCompanyEdit()" class="text-sm text-white bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg font-medium">Save</button>
      </div>
    </div>
  </div>

  <!-- Tabs -->
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200" x-show="company">
    <div class="border-b border-slate-200 px-6 flex gap-1">
      <button @click="companyTab='jobs'" :class="companyTab==='jobs' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-900'" class="px-3 py-3 text-sm font-medium border-b-2 -mb-px transition">
        Jobs <span class="text-xs text-slate-400 ml-1" x-text="'(' + (company?.total_jobs ?? 0) + ')'"></span>
      </button>
      <button @click="companyTab='tech'" :class="companyTab==='tech' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-900'" class="px-3 py-3 text-sm font-medium border-b-2 -mb-px transition">
        Tech Stack <span class="text-xs text-slate-400 ml-1" x-text="'(' + (company?.systems_count ?? 0) + ')'"></span>
      </button>
      <button @click="companyTab='scrapes'; loadCompanyScrapes()" :class="companyTab==='scrapes' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-900'" class="px-3 py-3 text-sm font-medium border-b-2 -mb-px transition">
        Scrape History <span class="text-xs text-slate-400 ml-1" x-text="'(' + (company?.scrape_count ?? 0) + ')'"></span>
      </button>
      <button @click="companyTab='notes'" :class="companyTab==='notes' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-900'" class="px-3 py-3 text-sm font-medium border-b-2 -mb-px transition">
        Notes <span class="text-xs text-slate-400 ml-1" x-text="'(' + (companyNotes?.length ?? 0) + ')'"></span>
      </button>
    </div>

    <div class="p-6">

      <!-- Jobs tab -->
      <div x-show="companyTab==='jobs'">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-slate-500 bg-slate-50">
                <th class="font-medium py-2.5 px-3">Title</th>
                <th class="font-medium py-2.5 px-3">Location</th>
                <th class="font-medium py-2.5 px-3">Department</th>
                <th class="font-medium py-2.5 px-3">Posted</th>
                <th class="font-medium py-2.5 px-3">Status</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <template x-for="j in companyJobs" :key="j.id">
                <tr class="hover:bg-slate-50 cursor-pointer" @click="openJobSlideOver(j)">
                  <td class="py-2.5 px-3 text-slate-900 font-medium" x-text="j.title"></td>
                  <td class="py-2.5 px-3 text-slate-600" x-text="j.location || '—'"></td>
                  <td class="py-2.5 px-3 text-slate-600" x-text="j.department || '—'"></td>
                  <td class="py-2.5 px-3 text-slate-500 text-xs" x-text="j.posted_date ? new Date(j.posted_date).toLocaleDateString() : '—'"></td>
                  <td class="py-2.5 px-3">
                    <span :class="j.is_active ? 'bg-green-50 text-green-700' : 'bg-slate-100 text-slate-500'" class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium" x-text="j.is_active ? 'Active' : 'Inactive'"></span>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <div x-show="companyJobs.length === 0" class="py-8 text-center text-slate-400 text-sm">No jobs found for this company.</div>
      </div>

      <!-- Tech Stack tab -->
      <div x-show="companyTab==='tech'">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-slate-500 bg-slate-50">
                <th class="font-medium py-2.5 px-3">System</th>
                <th class="font-medium py-2.5 px-3">Category</th>
                <th class="font-medium py-2.5 px-3">Confidence</th>
                <th class="font-medium py-2.5 px-3">Keywords</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <template x-for="s in companySystems" :key="s.id">
                <tr class="hover:bg-slate-50">
                  <td class="py-2.5 px-3 text-slate-900 font-medium" x-text="s.system_name"></td>
                  <td class="py-2.5 px-3">
                    <span class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium"
                      :class="categoryColor(s.category)"
                      x-text="s.category"></span>
                  </td>
                  <td class="py-2.5 px-3">
                    <div class="flex items-center gap-2">
                      <div class="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div class="h-full bg-blue-500 rounded-full" :style="'width:' + Math.round((s.confidence || 0) * 100) + '%'"></div>
                      </div>
                      <span class="text-xs text-slate-500" x-text="Math.round((s.confidence || 0) * 100) + '%'"></span>
                    </div>
                  </td>
                  <td class="py-2.5 px-3">
                    <div class="flex flex-wrap gap-1">
                      <template x-for="kw in (Array.isArray(s.matched_keywords) ? s.matched_keywords : [])" :key="kw">
                        <span class="inline-flex px-1.5 py-0.5 rounded text-xs bg-slate-100 text-slate-600" x-text="kw"></span>
                      </template>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <div x-show="companySystems.length === 0" class="py-8 text-center text-slate-400 text-sm">No tech systems detected yet.</div>
      </div>

      <!-- Scrape History tab -->
      <div x-show="companyTab==='scrapes'">
        <div class="mb-4">
          <button @click="rescrapeCompany(company)" class="text-sm text-white bg-blue-600 hover:bg-blue-700 px-4 py-1.5 rounded-lg font-medium">Re-scrape</button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-slate-500 bg-slate-50">
                <th class="font-medium py-2.5 px-3">Date</th>
                <th class="font-medium py-2.5 px-3">Parser</th>
                <th class="font-medium py-2.5 px-3">Jobs Found</th>
                <th class="font-medium py-2.5 px-3">Elapsed</th>
                <th class="font-medium py-2.5 px-3">Deep</th>
                <th class="font-medium py-2.5 px-3">Error</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <template x-for="s in companyScrapes" :key="s.id">
                <tr class="hover:bg-slate-50">
                  <td class="py-2.5 px-3 text-slate-600 text-xs" x-text="s.created_at ? new Date(s.created_at).toLocaleString() : '—'"></td>
                  <td class="py-2.5 px-3 text-slate-900" x-text="s.parser_used || '—'"></td>
                  <td class="py-2.5 px-3 text-slate-600" x-text="s.jobs_found"></td>
                  <td class="py-2.5 px-3 text-slate-500 text-xs" x-text="s.elapsed_ms + 'ms'"></td>
                  <td class="py-2.5 px-3">
                    <span :class="s.deep ? 'text-blue-600' : 'text-slate-300'" x-text="s.deep ? 'Yes' : 'No'" class="text-xs"></span>
                  </td>
                  <td class="py-2.5 px-3 text-xs text-red-600" x-text="s.error || '—'"></td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <div x-show="companyScrapes.length === 0" class="py-8 text-center text-slate-400 text-sm">No scrape history yet.</div>
      </div>

      <!-- Notes tab -->
      <div x-show="companyTab==='notes'">
        <div class="mb-4">
          <div class="flex gap-2">
            <textarea x-model="newNote" placeholder="Add a note..." rows="2"
              class="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"></textarea>
            <button @click="addNote()" :disabled="!newNote.trim()" class="self-end text-sm text-white bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg font-medium disabled:opacity-50">Add</button>
          </div>
        </div>
        <div class="space-y-2">
          <template x-for="n in companyNotes" :key="n.id">
            <div class="flex items-start justify-between gap-3 p-3 rounded-lg border border-slate-100 bg-slate-50">
              <div>
                <p class="text-sm text-slate-900" x-text="n.note"></p>
                <p class="text-xs text-slate-400 mt-1" x-text="n.created_at ? new Date(n.created_at).toLocaleString() : ''"></p>
              </div>
              <button @click="deleteNote(n.id)" class="text-slate-400 hover:text-red-500 shrink-0" title="Delete">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
              </button>
            </div>
          </template>
        </div>
        <div x-show="companyNotes.length === 0 && !newNote" class="py-8 text-center text-slate-400 text-sm">No notes yet.</div>
      </div>

    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════ -->
<!-- PAGE 3: JOB LISTINGS                                -->
<!-- ═══════════════════════════════════════════════════ -->
<div x-show="page==='jobs'" x-cloak>
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
    <div class="flex flex-col md:flex-row items-start md:items-center gap-3 mb-4">
      <h2 class="text-lg font-bold text-slate-900">Jobs</h2>
      <div class="flex-1"></div>
      <input x-model.debounce.300ms="jobsSearch" @input="loadJobs()" type="text" placeholder="Search jobs..."
        class="w-full md:w-56 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
      <select x-model="jobsCompany" @change="loadJobs()" class="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="">All companies</option>
        <template x-for="c in jobsCompanyList" :key="c.id">
          <option :value="c.id" x-text="c.name"></option>
        </template>
      </select>
      <select x-model="jobsDept" @change="loadJobs()" class="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="">All departments</option>
        <template x-for="d in departments" :key="d">
          <option :value="d" x-text="d"></option>
        </template>
      </select>
      <div class="flex items-center gap-1 border border-slate-200 rounded-lg overflow-hidden">
        <button @click="jobsActive = null; loadJobs()" :class="jobsActive === null ? 'bg-blue-50 text-blue-700' : 'text-slate-600'" class="px-3 py-1.5 text-xs font-medium">All</button>
        <button @click="jobsActive = true; loadJobs()" :class="jobsActive === true ? 'bg-green-50 text-green-700' : 'text-slate-600'" class="px-3 py-1.5 text-xs font-medium">Active</button>
        <button @click="jobsActive = false; loadJobs()" :class="jobsActive === false ? 'bg-slate-100 text-slate-600' : 'text-slate-600'" class="px-3 py-1.5 text-xs font-medium">Inactive</button>
      </div>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-slate-500 bg-slate-50">
            <th class="font-medium py-2.5 px-3">Title</th>
            <th class="font-medium py-2.5 px-3">Company</th>
            <th class="font-medium py-2.5 px-3">Location</th>
            <th class="font-medium py-2.5 px-3">Department</th>
            <th class="font-medium py-2.5 px-3">Posted</th>
            <th class="font-medium py-2.5 px-3">Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <template x-for="j in allJobs" :key="j.id">
            <tr class="hover:bg-slate-50 cursor-pointer" @click="openJobSlideOver(j)">
              <td class="py-2.5 px-3 text-slate-900 font-medium" x-text="j.title"></td>
              <td class="py-2.5 px-3">
                <button @click.stop="navigate('company', j.company_id)" class="text-blue-600 hover:text-blue-800" x-text="j.company_name || '—'"></button>
              </td>
              <td class="py-2.5 px-3 text-slate-600" x-text="j.location || '—'"></td>
              <td class="py-2.5 px-3 text-slate-600" x-text="j.department || '—'"></td>
              <td class="py-2.5 px-3 text-slate-500 text-xs" x-text="j.posted_date ? new Date(j.posted_date).toLocaleDateString() : '—'"></td>
              <td class="py-2.5 px-3">
                <span :class="j.is_active ? 'bg-green-50 text-green-700' : 'bg-slate-100 text-slate-500'" class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium" x-text="j.is_active ? 'Active' : 'Inactive'"></span>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div x-show="allJobs.length === 0 && !loading" class="py-8 text-center text-slate-400 text-sm">No jobs found.</div>
    <div x-show="loading" class="py-8 text-center text-slate-400 text-sm">Loading...</div>

    <!-- Pagination -->
    <div class="flex items-center justify-between mt-4 pt-4 border-t border-slate-100" x-show="jobsTotal > 0">
      <span class="text-xs text-slate-500" x-text="'Showing ' + allJobs.length + ' of ' + jobsTotal"></span>
      <div class="flex gap-1">
        <button @click="jobsPage--; loadJobs()" :disabled="jobsPage <= 1" class="px-3 py-1 text-xs border border-slate-200 rounded-lg disabled:opacity-30 hover:bg-slate-50">Prev</button>
        <span class="px-3 py-1 text-xs text-slate-500" x-text="'Page ' + jobsPage"></span>
        <button @click="jobsPage++; loadJobs()" :disabled="allJobs.length < 50" class="px-3 py-1 text-xs border border-slate-200 rounded-lg disabled:opacity-30 hover:bg-slate-50">Next</button>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════ -->
<!-- PAGE 4: INTELLIGENCE                                -->
<!-- ═══════════════════════════════════════════════════ -->
<div x-show="page==='intelligence'" x-cloak>

  <!-- Tech Stack Heatmap -->
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
    <h2 class="text-lg font-bold text-slate-900 mb-4">Tech Stack Heatmap</h2>
    <div x-show="heatmap && heatmap.companies.length > 0" class="overflow-x-auto">
      <table class="text-xs">
        <thead>
          <tr>
            <th class="font-medium py-2 px-2 text-left text-slate-500 sticky left-0 bg-white">System</th>
            <th class="font-medium py-2 px-2 text-left text-slate-500 sticky left-0 bg-white">Category</th>
            <template x-for="c in heatmap.companies" :key="c.id">
              <th class="font-medium py-2 px-1 text-center min-w-[60px]">
                <button @click="navigate('company', c.id)" class="text-blue-600 hover:underline truncate block max-w-[80px]" :title="c.name" x-text="c.name.substring(0, 10)"></button>
              </th>
            </template>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <template x-for="sys in heatmapSystems" :key="sys.key">
            <tr>
              <td class="py-1.5 px-2 text-slate-900 font-medium sticky left-0 bg-white" x-text="sys.name"></td>
              <td class="py-1.5 px-2 sticky left-0 bg-white">
                <span class="inline-flex px-1.5 py-0.5 rounded-full text-xs font-medium" :class="categoryColor(sys.category)" x-text="sys.category"></span>
              </td>
              <template x-for="c in heatmap.companies" :key="c.id">
                <td class="py-1.5 px-1 text-center">
                  <div class="w-6 h-6 rounded mx-auto" :class="getHeatmapCell(sys.key, c.id) ? 'bg-blue-500' : 'bg-slate-50'" :style="getHeatmapCell(sys.key, c.id) ? 'opacity:' + (0.3 + getHeatmapCell(sys.key, c.id).confidence * 0.7) : ''" :title="getHeatmapCell(sys.key, c.id) ? Math.round(getHeatmapCell(sys.key, c.id).confidence * 100) + '%' : ''"></div>
                </td>
              </template>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <div x-show="!heatmap || heatmap.companies.length === 0" class="py-8 text-center text-slate-400 text-sm">No tech stack data yet. Scrape some companies first.</div>
  </div>

  <!-- Hiring Trends -->
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
    <h2 class="text-lg font-bold text-slate-900 mb-4">Hiring Trends</h2>
    <div x-show="companies.length > 0" class="space-y-2">
      <template x-for="c in companies" :key="c.id">
        <div class="flex items-center justify-between p-3 rounded-lg border border-slate-100 hover:bg-slate-50">
          <div class="flex items-center gap-3">
            <button @click="navigate('company', c.id)" class="text-sm font-medium text-blue-600 hover:text-blue-800" x-text="c.name"></button>
            <span x-show="c.region" class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700" x-text="c.region"></span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium" :class="c.jobs_count > 0 ? 'text-green-600' : 'text-slate-400'" x-text="c.jobs_count + ' active'"></span>
            <span x-show="c.jobs_count > 0" class="text-green-500">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"/></svg>
            </span>
            <span x-show="c.jobs_count === 0 && c.total_jobs > 0" class="text-red-500">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"/></svg>
            </span>
            <span x-show="c.jobs_count === 0 && c.total_jobs === 0" class="text-slate-300">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4"/></svg>
            </span>
          </div>
        </div>
      </template>
    </div>
    <div x-show="companies.length === 0" class="py-8 text-center text-slate-400 text-sm">No company data yet.</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════ -->
<!-- PAGE 5: SCRAPE                                      -->
<!-- ═══════════════════════════════════════════════════ -->
<div x-show="page==='scrape'" x-cloak>

  <!-- Scrape form -->
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
    <h2 class="text-lg font-bold text-slate-900 mb-1">Scrape a careers page</h2>
    <p class="text-sm text-slate-500 mb-4">Paste any ATS URL — Paylocity, UKG/Ultipro, SmartRecruiters, Greenhouse, Lever, iCIMS, Workday, or generic.</p>

    <div class="space-y-3">
      <div>
        <label class="text-sm font-medium text-slate-700">URL *</label>
        <input x-model="scrapeUrl" type="text" placeholder="https://boards.greenhouse.io/embed/job_board?for=stripe"
          class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          @keydown.enter="runScrape()">
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="text-sm font-medium text-slate-700">Company name (optional)</label>
          <input x-model="scrapeCompany" type="text" placeholder="Auto-detected"
            class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
        <div>
          <label class="text-sm font-medium text-slate-700">Timeout (ms)</label>
          <input x-model.number="scrapeTimeout" type="number" step="1000"
            class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        </div>
      </div>
      <div class="flex items-center gap-4">
        <label class="flex items-center gap-2 text-sm text-slate-700">
          <input x-model="scrapeDeep" type="checkbox" class="rounded border-slate-300">
          Deep scrape (fetch job details)
        </label>
        <label class="flex items-center gap-2 text-sm text-slate-700">
          <input x-model="scrapeDebug" type="checkbox" class="rounded border-slate-300">
          Debug mode
        </label>
      </div>
    </div>

    <div class="mt-4 flex items-center gap-3">
      <button @click="runScrape()" :disabled="scrapeLoading || !scrapeUrl"
        class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-5 py-2 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed">
        <span x-show="!scrapeLoading">Scrape</span>
        <span x-show="scrapeLoading">Scraping...</span>
      </button>
      <button @click="clearScrape()" class="text-sm text-slate-600 hover:text-slate-900">Clear</button>
      <span x-show="scrapeResult" class="text-xs text-slate-500" x-text="scrapeResult ? 'Method: ' + scrapeResult.method + ' | ' + scrapeResult.elapsed_ms + 'ms | ' + scrapeResult.jobs_count + ' jobs' : ''"></span>
    </div>

    <div x-show="scrapeError" class="mt-4 px-3 py-2 rounded-lg text-sm bg-red-50 text-red-700 border border-red-200" x-text="scrapeError"></div>
  </div>

  <!-- Scrape results -->
  <div x-show="scrapeResult && scrapeResult.jobs && scrapeResult.jobs.length > 0" class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-bold text-slate-900">Results <span class="text-slate-400 font-normal" x-text="'(' + (scrapeResult?.jobs?.length || 0) + ')'"></span></h2>
      <div class="flex gap-2">
        <button @click="copyScrapeJSON()" class="text-xs text-slate-600 hover:text-slate-900 border border-slate-200 px-3 py-1 rounded-lg">Copy JSON</button>
        <button @click="saveScrapeResults()" class="text-xs text-white bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded-lg font-medium">
          <span x-text="scrapeLinkedCompany ? 'Link to ' + scrapeLinkedCompany.name : 'Save to Company'"></span>
        </button>
      </div>
    </div>
    <div x-show="scrapeSaveSuccess" class="mb-3 px-3 py-2 rounded-lg text-sm bg-green-50 text-green-700 border border-green-200" x-text="scrapeSaveSuccess"></div>

    <!-- Save as new company form -->
    <div x-show="showSaveForm && !scrapeLinkedCompany" class="mb-4 p-4 rounded-lg border border-blue-200 bg-blue-50">
      <p class="text-sm text-blue-800 mb-2">Create new company to save jobs:</p>
      <div class="flex gap-2">
        <input x-model="saveCompanyName" type="text" placeholder="Company name"
          class="flex-1 border border-blue-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
        <button @click="doSaveScrape()" :disabled="!saveCompanyName.trim()" class="text-sm text-white bg-blue-600 hover:bg-blue-700 px-4 py-1.5 rounded-lg font-medium disabled:opacity-50">Create & Save</button>
      </div>
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
          <template x-for="(job, i) in scrapeResult.jobs" :key="i">
            <tr class="border-b border-slate-100 hover:bg-slate-50">
              <td class="py-2 pr-4 text-slate-900" x-text="job.title"></td>
              <td class="py-2 pr-4 text-slate-600" x-text="job.location || '—'"></td>
              <td class="py-2"><a x-show="job.url" :href="job.url" target="_blank" class="text-blue-600 hover:underline">Open</a></td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>

  <div x-show="scrapeResult && scrapeResult.jobs && scrapeResult.jobs.length === 0 && !scrapeError" class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 text-center text-slate-500 text-sm mb-6">
    No jobs found. Try debug mode to inspect the page HTML.
  </div>

  <!-- Debug HTML -->
  <div x-show="scrapeResult?.html_sample" class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
    <h2 class="text-sm font-bold text-slate-900 mb-2">HTML sample <span class="text-slate-400 font-normal" x-text="'(' + (scrapeResult?.html_size?.toLocaleString() || 0) + ' bytes total)'"></span></h2>
    <pre class="text-xs bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-x-auto max-h-96 overflow-y-auto" x-text="scrapeResult?.html_sample"></pre>
  </div>

  <!-- Recent scrapes from DB -->
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
    <h2 class="text-sm font-bold text-slate-900 mb-3">Recent Scrapes</h2>
    <div x-show="recentScrapes.length > 0" class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-slate-500 bg-slate-50">
            <th class="font-medium py-2 px-3">Date</th>
            <th class="font-medium py-2 px-3">Company</th>
            <th class="font-medium py-2 px-3">URL</th>
            <th class="font-medium py-2 px-3">Parser</th>
            <th class="font-medium py-2 px-3">Jobs</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <template x-for="s in recentScrapes" :key="s.id">
            <tr class="hover:bg-slate-50">
              <td class="py-2 px-3 text-xs text-slate-500" x-text="s.created_at ? new Date(s.created_at).toLocaleString() : '—'"></td>
              <td class="py-2 px-3">
                <button x-show="s.company_id" @click="navigate('company', s.company_id)" class="text-blue-600 hover:underline text-sm" x-text="s.company_name || '—'"></button>
                <span x-show="!s.company_id" class="text-slate-400 text-sm">—</span>
              </td>
              <td class="py-2 px-3 text-xs text-slate-500 max-w-[200px] truncate" x-text="s.url"></td>
              <td class="py-2 px-3 text-sm text-slate-600" x-text="s.parser_used || '—'"></td>
              <td class="py-2 px-3 text-sm text-slate-600" x-text="s.jobs_found"></td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <div x-show="recentScrapes.length === 0" class="py-6 text-center text-slate-400 text-sm">No scrapes saved yet.</div>
  </div>
</div>

</main>

<!-- ═══ JOB SLIDE-OVER ═══ -->
<div x-show="selectedJob" class="fixed inset-0 z-50" x-cloak>
  <div class="absolute inset-0 bg-black/20" @click="selectedJob = null"></div>
  <div class="absolute right-0 top-0 bottom-0 w-full max-w-lg bg-white shadow-xl border-l border-slate-200 overflow-y-auto"
    x-transition:enter="transition ease-out duration-200"
    x-transition:enter-start="translate-x-full"
    x-transition:enter-end="translate-x-0"
    x-transition:leave="transition ease-in duration-150"
    x-transition:leave-start="translate-x-0"
    x-transition:leave-end="translate-x-full">
    <div class="p-6">
      <div class="flex items-start justify-between mb-4">
        <h2 class="text-lg font-bold text-slate-900 pr-4" x-text="selectedJob?.title"></h2>
        <button @click="selectedJob = null" class="text-slate-400 hover:text-slate-900 shrink-0">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>

      <div class="space-y-4 text-sm">
        <div x-show="selectedJob?.company_name">
          <div class="text-xs font-medium text-slate-500 mb-0.5">Company</div>
          <button @click="navigate('company', selectedJob.company_id); selectedJob = null" class="text-blue-600 hover:underline" x-text="selectedJob?.company_name"></button>
        </div>
        <div x-show="selectedJob?.location">
          <div class="text-xs font-medium text-slate-500 mb-0.5">Location</div>
          <div class="text-slate-900" x-text="selectedJob?.location"></div>
        </div>
        <div x-show="selectedJob?.department">
          <div class="text-xs font-medium text-slate-500 mb-0.5">Department</div>
          <div class="text-slate-900" x-text="selectedJob?.department"></div>
        </div>
        <div x-show="selectedJob?.full_address">
          <div class="text-xs font-medium text-slate-500 mb-0.5">Full Address</div>
          <div class="text-slate-900" x-text="selectedJob?.full_address"></div>
          <a x-show="selectedJob?.maps_url" :href="selectedJob?.maps_url" target="_blank" class="text-blue-600 hover:underline text-xs mt-1 inline-block">View on Maps</a>
        </div>
        <div x-show="selectedJob?.posted_date">
          <div class="text-xs font-medium text-slate-500 mb-0.5">Posted Date</div>
          <div class="text-slate-900" x-text="selectedJob?.posted_date"></div>
        </div>
        <div>
          <div class="text-xs font-medium text-slate-500 mb-0.5">Status</div>
          <span :class="selectedJob?.is_active ? 'bg-green-50 text-green-700' : 'bg-slate-100 text-slate-500'" class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium" x-text="selectedJob?.is_active ? 'Active' : 'Inactive'"></span>
        </div>
        <div x-show="selectedJob?.description">
          <div class="text-xs font-medium text-slate-500 mb-1">Description</div>
          <div class="text-slate-700 whitespace-pre-wrap text-xs leading-relaxed bg-slate-50 rounded-lg p-3 max-h-64 overflow-y-auto" x-text="selectedJob?.description"></div>
        </div>
        <div x-show="selectedJob?.requirements">
          <div class="text-xs font-medium text-slate-500 mb-1">Requirements</div>
          <div class="bg-slate-50 rounded-lg p-3 max-h-48 overflow-y-auto">
            <template x-if="Array.isArray(selectedJobRequirements)">
              <ul class="list-disc list-inside text-xs text-slate-700 space-y-1">
                <template x-for="(req, i) in selectedJobRequirements" :key="i">
                  <li x-text="req"></li>
                </template>
              </ul>
            </template>
            <template x-if="!Array.isArray(selectedJobRequirements) && selectedJob?.requirements">
              <div class="text-xs text-slate-700 whitespace-pre-wrap" x-text="selectedJob?.requirements"></div>
            </template>
          </div>
        </div>
        <div x-show="selectedJob?.url" class="pt-2 border-t border-slate-100">
          <a :href="selectedJob?.url" target="_blank" class="text-blue-600 hover:underline text-sm font-medium">View original listing</a>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
function app() {
  return {
    page: 'overview',
    companyId: null,
    companyTab: 'jobs',

    // Overview
    stats: null,
    companies: [],
    companiesTotal: 0,
    companiesSearch: '',
    companiesRegion: '',
    regions: [],

    // Company detail
    company: null,
    companyJobs: [],
    companyScrapes: [],
    companySystems: [],
    companyNotes: [],
    editModal: false,
    editForm: { name: '', website_url: '', careers_url: '', parent_company_name: '', region: '' },
    newNote: '',

    // Jobs page
    allJobs: [],
    jobsTotal: 0,
    jobsSearch: '',
    jobsDept: '',
    jobsCompany: '',
    jobsActive: null,
    jobsPage: 1,
    departments: [],
    jobsCompanyList: [],
    selectedJob: null,

    // Intelligence
    heatmap: null,
    heatmapSystems: [],
    heatmapLookup: {},

    // Scrape page
    scrapeUrl: '',
    scrapeCompany: '',
    scrapeTimeout: 30000,
    scrapeDeep: false,
    scrapeDebug: false,
    scrapeLoading: false,
    scrapeResult: null,
    scrapeError: '',
    scrapeLinkedCompany: null,
    showSaveForm: false,
    saveCompanyName: '',
    scrapeSaveSuccess: '',
    recentScrapes: [],

    loading: false,

    get selectedJobRequirements() {
      if (!this.selectedJob?.requirements) return null;
      try {
        const parsed = JSON.parse(this.selectedJob.requirements);
        if (Array.isArray(parsed)) return parsed;
      } catch {}
      return this.selectedJob.requirements;
    },

    navigate(page, id) {
      this.page = page;
      if (id) this.companyId = id;
      window.location.hash = id ? '#/' + page + '/' + id : '#/' + page;
      this.selectedJob = null;
      this.loadPage();
    },

    init() {
      const hash = window.location.hash.slice(2) || 'overview';
      const parts = hash.split('/');
      this.page = parts[0] || 'overview';
      if (parts[1]) this.companyId = parts[1];
      this.loadPage();
    },

    async loadPage() {
      this.loading = true;
      if (this.page === 'overview') {
        await Promise.all([this.loadStats(), this.loadCompanies()]);
      } else if (this.page === 'company') {
        await this.loadCompanyDetail();
      } else if (this.page === 'jobs') {
        this.jobsPage = 1;
        await this.loadJobs();
        await this.loadJobsCompanyList();
      } else if (this.page === 'intelligence') {
        await Promise.all([this.loadCompanies(), this.loadHeatmap()]);
      } else if (this.page === 'scrape') {
        await this.loadRecentScrapes();
      }
      this.loading = false;
    },

    async apiFetch(url, opts) {
      const res = await fetch(url, { credentials: 'same-origin', ...opts });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'HTTP ' + res.status);
      }
      return res.json();
    },

    // ── Overview ──
    async loadStats() {
      try {
        this.stats = await this.apiFetch('/api/stats');
      } catch {}
    },

    async loadCompanies() {
      try {
        const params = new URLSearchParams();
        if (this.companiesSearch) params.set('search', this.companiesSearch);
        if (this.companiesRegion) params.set('region', this.companiesRegion);
        const data = await this.apiFetch('/api/companies?' + params);
        this.companies = data.companies;
        this.companiesTotal = data.total;
        this.regions = data.regions || [];
      } catch {}
    },

    // ── Company detail ──
    async loadCompanyDetail() {
      if (!this.companyId) return;
      try {
        this.company = await this.apiFetch('/api/companies/' + this.companyId);
        this.companyNotes = this.company.notes || [];
        this.companySystems = this.company.systems || [];
        this.editForm = {
          name: this.company.name || '',
          website_url: this.company.website_url || '',
          careers_url: this.company.careers_url || '',
          parent_company_name: this.company.parent_company_name || '',
          region: this.company.region || '',
        };
        await this.loadCompanyJobs();
      } catch (e) {
        console.error('loadCompanyDetail', e);
      }
    },

    async loadCompanyJobs() {
      try {
        const data = await this.apiFetch('/api/companies/' + this.companyId + '/jobs');
        this.companyJobs = data.jobs || [];
      } catch {}
    },

    async loadCompanyScrapes() {
      try {
        this.companyScrapes = await this.apiFetch('/api/companies/' + this.companyId + '/scrapes');
      } catch {}
    },

    async saveCompanyEdit() {
      try {
        const body = {};
        for (const [k, v] of Object.entries(this.editForm)) {
          if (v) body[k] = v;
        }
        this.company = await this.apiFetch('/api/companies/' + this.companyId, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        this.editModal = false;
      } catch (e) {
        alert('Error: ' + e.message);
      }
    },

    async addNote() {
      if (!this.newNote.trim()) return;
      try {
        const n = await this.apiFetch('/api/companies/' + this.companyId + '/notes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note: this.newNote.trim() }),
        });
        this.companyNotes.unshift(n);
        this.newNote = '';
      } catch (e) {
        alert('Error: ' + e.message);
      }
    },

    async deleteNote(noteId) {
      try {
        await this.apiFetch('/api/companies/' + this.companyId + '/notes/' + noteId, { method: 'DELETE' });
        this.companyNotes = this.companyNotes.filter(n => n.id !== noteId);
      } catch {}
    },

    // ── Jobs page ──
    async loadJobs() {
      try {
        const params = new URLSearchParams();
        if (this.jobsSearch) params.set('search', this.jobsSearch);
        if (this.jobsCompany) params.set('company_id', this.jobsCompany);
        if (this.jobsDept) params.set('department', this.jobsDept);
        if (this.jobsActive !== null) params.set('is_active', this.jobsActive);
        params.set('page', this.jobsPage);
        const data = await this.apiFetch('/api/jobs?' + params);
        this.allJobs = data.jobs;
        this.jobsTotal = data.total;
        this.departments = data.departments || [];
      } catch {}
    },

    async loadJobsCompanyList() {
      try {
        const data = await this.apiFetch('/api/companies?limit=200');
        this.jobsCompanyList = data.companies || [];
      } catch {}
    },

    openJobSlideOver(job) {
      if (job.description || job.snippet) {
        this.selectedJob = job;
      } else {
        this.apiFetch('/api/jobs/' + job.id).then(full => {
          this.selectedJob = full;
        }).catch(() => {
          this.selectedJob = job;
        });
      }
    },

    // ── Intelligence ──
    async loadHeatmap() {
      try {
        this.heatmap = await this.apiFetch('/api/systems-heatmap');
        const systemMap = {};
        this.heatmapLookup = {};
        for (const s of this.heatmap.systems) {
          const key = s.system_name + '|' + s.category;
          if (!systemMap[key]) {
            systemMap[key] = { key, name: s.system_name, category: s.category };
          }
          this.heatmapLookup[key + '|' + s.company_id] = s;
        }
        this.heatmapSystems = Object.values(systemMap);
      } catch {}
    },

    getHeatmapCell(sysKey, companyId) {
      return this.heatmapLookup[sysKey + '|' + companyId] || null;
    },

    categoryColor(cat) {
      const map = {
        'ats': 'bg-blue-50 text-blue-700',
        'crm': 'bg-purple-50 text-purple-700',
        'hris': 'bg-green-50 text-green-700',
        'payroll': 'bg-amber-50 text-amber-700',
        'analytics': 'bg-cyan-50 text-cyan-700',
        'communication': 'bg-pink-50 text-pink-700',
        'benefits': 'bg-emerald-50 text-emerald-700',
        'scheduling': 'bg-orange-50 text-orange-700',
      };
      return map[(cat || '').toLowerCase()] || 'bg-slate-100 text-slate-700';
    },

    // ── Scrape ──
    async runScrape() {
      this.scrapeError = '';
      this.scrapeResult = null;
      this.scrapeLinkedCompany = null;
      this.showSaveForm = false;
      this.scrapeSaveSuccess = '';
      this.scrapeLoading = true;
      let url = this.scrapeUrl.trim();
      if (!url.startsWith('http')) url = 'https://' + url;
      try {
        const r = await fetch('/scrape', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({
            url,
            company_name: this.scrapeCompany || undefined,
            timeout: this.scrapeTimeout,
            deep: this.scrapeDeep,
            debug: this.scrapeDebug,
          }),
        });
        const d = await r.json();
        if (!r.ok) {
          this.scrapeError = d.detail || 'HTTP ' + r.status;
        } else {
          this.scrapeResult = d;
          this.saveCompanyName = this.scrapeCompany || d.company_name || '';
          await this.checkLinkedCompany(url);
        }
      } catch (e) {
        this.scrapeError = 'Network error: ' + e.message;
      }
      this.scrapeLoading = false;
    },

    async checkLinkedCompany(url) {
      try {
        const data = await this.apiFetch('/api/companies?search=' + encodeURIComponent(url) + '&limit=1');
        if (data.companies.length > 0) {
          this.scrapeLinkedCompany = data.companies[0];
        }
      } catch {}
    },

    clearScrape() {
      this.scrapeUrl = '';
      this.scrapeCompany = '';
      this.scrapeResult = null;
      this.scrapeError = '';
      this.scrapeLinkedCompany = null;
      this.showSaveForm = false;
      this.scrapeSaveSuccess = '';
    },

    copyScrapeJSON() {
      navigator.clipboard.writeText(JSON.stringify(this.scrapeResult, null, 2));
    },

    saveScrapeResults() {
      if (this.scrapeLinkedCompany) {
        this.doSaveScrape(this.scrapeLinkedCompany.id);
      } else {
        this.showSaveForm = true;
      }
    },

    async doSaveScrape(existingCompanyId) {
      try {
        const body = {
          careers_url: this.scrapeUrl.trim(),
          parser_used: this.scrapeResult.method || '',
          jobs_found: this.scrapeResult.jobs_count || 0,
          elapsed_ms: this.scrapeResult.elapsed_ms || 0,
          html_size: this.scrapeResult.html_size || 0,
          deep: this.scrapeDeep,
          jobs: this.scrapeResult.jobs || [],
          html: this.scrapeResult.html_sample || '',
        };
        if (existingCompanyId) {
          body.company_id = existingCompanyId;
        } else {
          body.company_name = this.saveCompanyName.trim();
        }
        const result = await this.apiFetch('/api/save-scrape', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        this.scrapeSaveSuccess = 'Saved! ' + (result.company?.name || '') + ' — ' + (this.scrapeResult.jobs_count || 0) + ' jobs.';
        this.showSaveForm = false;
        this.loadRecentScrapes();
      } catch (e) {
        alert('Error saving: ' + e.message);
      }
    },

    async loadRecentScrapes() {
      try {
        this.recentScrapes = await this.apiFetch('/api/recent-scrapes');
      } catch {
        this.recentScrapes = [];
      }
    },

    async rescrapeCompany(c) {
      if (!c?.careers_url) {
        alert('No careers URL set for this company.');
        return;
      }
      this.navigate('scrape');
      await this.$nextTick;
      this.scrapeUrl = c.careers_url;
      this.scrapeCompany = c.name;
    },
  };
}
</script>
</body>
</html>"""


def scraper_page() -> str:
    return SCRAPER_HTML
