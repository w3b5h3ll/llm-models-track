'use strict';
const $ = (id) => document.getElementById(id);
const PROVIDERS = {
  anthropic: ['Anthropic', 'A', '#985f40', '#f7eee8'],
  deepseek: ['DeepSeek', 'D', '#3f64d6', '#edf2ff'],
  moonshotai: ['Moonshot AI', 'K', '#333f55', '#eef0f5'],
  openai: ['OpenAI', 'O', '#347c67', '#eaf4ef'],
  qwen: ['Qwen', 'Q', '#7651c8', '#f2edfc'],
  'x-ai': ['xAI', 'x', '#374155', '#edf0f4'],
  'z-ai': ['Z.ai', 'Z', '#415bc1', '#eef1fc'],
};
const MODALITIES = {text: '文本', image: '图像', audio: '音频', video: '视频', file: '文件', pdf: 'PDF'};
let data = null;
let checks = null;
let selectedModelId = null;
let detailTrigger = null;
const active = new Set();
const number = new Intl.NumberFormat('en-US');
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function compact(value) {
  if (!Number.isFinite(value)) return '未知';
  if (value >= 1e6) return `${Number((value / 1e6).toFixed(2))}M`;
  if (value >= 1e3) return `${Number((value / 1e3).toFixed(1))}K`;
  return number.format(value);
}
function full(value) { return Number.isFinite(value) ? number.format(value) : '未知'; }
function modalityText(values) { return Array.isArray(values) ? values.map(v => MODALITIES[v] || v).join('、') || '无' : '未知'; }
function boolText(value) { return value === true ? '支持' : value === false ? '不支持' : '未知'; }
function safeSource(url) {
  try { const parsed = new URL(url); return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : null; }
  catch { return null; }
}
function unknown(model) { return model.basis === 'official' ? '未列出' : '未知'; }
function metric(model, field, precise = false) {
  if (!Number.isFinite(model[field])) return unknown(model);
  const reported = model.basis === 'official' ? model.official?.field_sources?.[field]?.reported : null;
  if (reported && /[KM]/i.test(reported)) return reported + (precise ? '（官方简写）' : '');
  return precise ? full(model[field]) : compact(model[field]);
}
function currentModels() {
  return data.models.map(model => $('basis').value === 'platform' && model.platform
    ? {...model, ...model.platform, basis: 'platform'} : model);
}
function updateStats(models) {
  $('total').textContent = models.length;
  $('providers-count').textContent = new Set(models.map(m => m.provider)).size;
  $('multimodal-count').textContent = models.filter(m => m.input_modalities?.some(v => ['image', 'audio', 'video'].includes(v))).length;
  const limits = models.map(m => m.context_tokens).filter(Number.isFinite);
  $('max-context').textContent = limits.length ? compact(Math.max(...limits)) : '未知';
}
function openDetails(model) {
  selectedModelId = model.id;
  detailTrigger = document.activeElement;
  document.body.classList.add('detail-open');
  document.querySelectorAll('#models tr').forEach(row => row.classList.toggle('selected', row.dataset.modelId === model.id));
  $('detail-title').textContent = model.name.replace(/^[^:]+:\s*/, '');
  $('detail-id').textContent = model.id;
  $('detail-fields').replaceChildren();
  const fields = [
    ['厂商', (PROVIDERS[model.provider] || [model.provider])[0]],
    ['上下文', metric(model, 'context_tokens', true)],
    ['最大输入', model.basis === 'official' && model.max_input_tokens_thinking != null ? '按思考模式分别限定' : metric(model, 'max_input_tokens', true)],
    ['最大输出', metric(model, 'max_output_tokens', true)],
    ['输入模态', modalityText(model.input_modalities)],
    ['输出模态', modalityText(model.output_modalities)],
    ['工具调用', boolText(model.tool_call)], ['推理', boolText(model.reasoning)],
    ['数据口径', model.scope || '未知'],
  ];
  if (model.max_input_tokens_thinking != null && model.basis === 'official') fields.push(['最大输入 · 思考', full(model.max_input_tokens_thinking)], ['最大输入 · 非思考', full(model.max_input_tokens_non_thinking)]);
  if (model.context_extended_tokens != null && model.basis === 'official') fields.push(['可扩展上下文', full(model.context_extended_tokens)]);
  const checked = checks?.models?.[model.id];
  if (checked) fields.push(['本次官方核对', checked.status === 'verified' ? '已核对' : checked.message || '未核实']);
  for (const [key, value] of fields) $('detail-fields').append(element('dt', '', key), element('dd', '', value));
  const url = safeSource(model.source);
  $('detail-source').hidden = !url;
  if (url) $('detail-source').href = url;
  $('detail-comparison').replaceChildren();
  if (model.official && model.platform) {
    const title = element('h3', '', '官方 / 平台规格对照');
    const table = element('table', 'compare-table');
    const head = element('tr'); ['字段', '官方', '聚合平台'].forEach(v => head.append(element('th', '', v))); table.append(head);
    const official = {...model, ...model.official.values, basis: 'official'};
    const platform = {...model.platform, basis: 'platform'};
    for (const [field, label] of [['context_tokens','上下文'],['max_input_tokens','最大输入'],['max_output_tokens','最大输出']]) {
      const tr = element('tr');
      let officialValue = metric(official, field, true);
      if (field === 'max_input_tokens' && official.max_input_tokens_thinking != null) officialValue = `思考 ${full(official.max_input_tokens_thinking)} / 非思考 ${full(official.max_input_tokens_non_thinking)}`;
      tr.append(element('td','',label), element('td','',officialValue), element('td','',metric(platform,field,true))); table.append(tr);
    }
    $('detail-comparison').append(title, table);
  }
  $('detail-evidence').replaceChildren();
  $('evidence-panel').hidden = !model.official;
  $('evidence-panel').open = false;
  const labels = {context_tokens:'上下文',max_input_tokens:'最大输入',max_output_tokens:'最大输出',input_modalities:'输入模态',output_modalities:'输出模态',tool_call:'工具调用',reasoning:'推理',max_input_tokens_thinking:'最大输入 · 思考',max_input_tokens_non_thinking:'最大输入 · 非思考',context_extended_tokens:'扩展上下文'};
  for (const [field, evidence] of Object.entries(model.official?.field_sources || {})) {
    const block = element('div','evidence-item'); block.append(element('strong','',labels[field] || field),element('blockquote','',evidence.quote));
    const href = safeSource(evidence.url);
    if (href) {const link=element('a','','官方来源 ↗'); link.href=href; link.target='_blank'; link.rel='noopener noreferrer'; block.append(link);}
    $('detail-evidence').append(block);
  }
  if (!$('detail').open) $('detail').show();
}
function tags(values) {
  const box = element('div', 'tags');
  if (!Array.isArray(values)) { box.append(element('span', 'unknown', '未知')); return box; }
  if (!values.length) box.append(element('span', 'unknown', '无'));
  values.forEach(value => box.append(element('span', `tag${value === 'text' ? '' : ' rich'}`, MODALITIES[value] || value)));
  return box;
}
function filteredModels() {
  const query = $('search').value.trim().toLowerCase();
  const rows = currentModels().filter(model => {
    if ($('provider').value && model.provider !== $('provider').value) return false;
    if (query && !`${model.name} ${model.id} ${model.provider}`.toLowerCase().includes(query)) return false;
    return [...active].every(key => ['image', 'audio', 'video'].includes(key)
      ? Array.isArray(model.input_modalities) && model.input_modalities.includes(key) : model[key] === true);
  });
  const sort = $('sort').value;
  return rows.sort((a, b) => {
    if (sort !== 'name') {
      const field = sort.startsWith('context') ? 'context_tokens' : 'max_output_tokens';
      const av = a[field], bv = b[field];
      if (!Number.isFinite(av) && Number.isFinite(bv)) return 1;
      if (Number.isFinite(av) && !Number.isFinite(bv)) return -1;
      if (Number.isFinite(av) && Number.isFinite(bv) && av !== bv) return sort.endsWith('asc') ? av - bv : bv - av;
    }
    return a.name.localeCompare(b.name, 'en', {numeric: true});
  });
}
function render() {
  if (!data) return;
  const models = filteredModels();
  const visibleBasis = currentModels();
  updateStats(visibleBasis);
  const officialCount = visibleBasis.filter(m => m.basis === 'official').length;
  const staleCount = visibleBasis.filter(m => m.basis === 'official' && m.official?.status === 'stale').length;
  $('source-badge').textContent = `官方 ${officialCount} · 平台 ${visibleBasis.length - officialCount}` + (staleCount ? ` · 待复核 ${staleCount}` : '');
  $('models').replaceChildren();
  $('result-count').textContent = `${models.length} / ${data.models.length}`;
  $('status').textContent = '';
  $('status').classList.add('sr-only');
  $('status').textContent = `显示 ${models.length} 个模型，共 ${data.models.length} 个`;
  $('empty').hidden = models.length !== 0;
  const max = Math.max(1, ...data.models.map(m => m.context_tokens || 0));
  for (const model of models) {
    const tr = element('tr');
    tr.dataset.modelId = model.id;
    tr.classList.toggle('selected', model.id === selectedModelId && $('detail').open);
    const td = element('td');
    const identity = element('div', 'model-cell');
    const [name, monogram, color, tint] = PROVIDERS[model.provider] || [model.provider, model.provider.slice(0, 1).toUpperCase(), '#475570', '#eef1f7'];
    const avatar = element('span', 'avatar', monogram);
    avatar.setAttribute('aria-hidden', 'true'); avatar.style.setProperty('--color', color); avatar.style.setProperty('--tint', tint);
    const text = element('div');
    const button = element('button', 'model-button', model.name.replace(/^[^:]+:\s*/, ''));
    button.type = 'button'; button.title = model.id; button.addEventListener('click', () => openDetails(model));
    const providerLine = element('div', 'provider-name', name);
    const official = model.basis === 'official';
    const stale = official && model.official?.status === 'stale';
    providerLine.append(element('span', 'basis-badge ' + (stale ? 'stale' : official ? 'official' : 'platform'), stale ? '官方旧快照' : official ? model.official.label : '平台规格'));
    text.append(button, providerLine); identity.append(avatar, text); td.append(identity); tr.append(td);
    for (const field of ['context_tokens', 'max_input_tokens', 'max_output_tokens']) {
      const cell = element('td'); const value = element('span', 'token-number', metric(model, field));
      value.title = metric(model, field, true);
      if (field === 'max_input_tokens' && model.basis === 'official' && model.max_input_tokens_thinking != null) {
        value.textContent = full(model.max_input_tokens_thinking); value.title = `思考模式：${full(model.max_input_tokens_thinking)} tokens`; cell.append(value, element('small','mode-label','思考模式'));
        cell.append(element('span','token-number',full(model.max_input_tokens_non_thinking)),element('small','mode-label','非思考模式'));
      } else { cell.append(value); }
      if (field === 'context_tokens' && model.basis === 'official' && model.context_extended_tokens != null) cell.append(element('small','mode-label','原生 · 可扩展至 ' + compact(model.context_extended_tokens)));
      if (field === 'context_tokens' && Number.isFinite(model[field])) {
        const bar = element('div', 'token-bar'); bar.setAttribute('aria-hidden', 'true'); const fill = element('span'); fill.style.width = `${Math.min(100, model[field] / max * 100)}%`; bar.append(fill); cell.append(bar);
      }
      tr.append(cell);
    }
    for (const field of ['input_modalities', 'output_modalities']) { const cell = element('td'); cell.append(tags(model[field])); tr.append(cell); }
    for (const field of ['tool_call', 'reasoning']) { const cell = element('td'); cell.append(element('span', model[field] === true ? 'support' : model[field] === false ? 'unsupported' : 'unknown', boolText(model[field]))); tr.append(cell); }
    $('models').append(tr);
  }
}
function reset() {
  $('search').value = ''; $('provider').value = ''; $('sort').value = 'name'; active.clear();
  document.querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', 'false'));
  render();
}
async function load() {
  $('error').hidden = true; $('retry').disabled = true;
  $('status').classList.remove('sr-only'); $('status').textContent = '正在读取模型数据…';
  try {
    const response = await fetch('data/models.json', {cache: 'no-cache'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const incoming = await response.json();
    checks = await fetch('data/checks.json', {cache:'no-cache'}).then(r => r.ok ? r.json() : null).catch(() => null);
    if (!Array.isArray(incoming.models) || !incoming.models.every(m => m && typeof m.id === 'string' && typeof m.name === 'string' && typeof m.provider === 'string')) throw new Error('模型数据格式不正确');
    data = incoming;
    const providers = [...new Set(data.models.map(m => m.provider))].sort();
    $('provider').replaceChildren(new Option('全部厂商', ''));
    providers.forEach(p => $('provider').append(new Option((PROVIDERS[p] || [p])[0], p)));
    updateStats(currentModels());
    const date = new Date(data.changed_at);
    $('updated').textContent = Number.isNaN(date.getTime()) ? '未知' : new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false}).format(date) + ' 北京时间';
    if (!Number.isNaN(date.getTime())) $('updated').dateTime = date.toISOString();
    const officialCount = data.models.filter(m => m.basis === 'official').length;
    const staleCount = data.models.filter(m => m.official?.status === 'stale').length;
    const checkedDate = new Date(checks?.checked_at || '');
    $('checked-at').textContent = Number.isNaN(checkedDate.getTime()) ? '最近检查时间暂不可用' : '最近检查：' + new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(checkedDate) + ' 北京时间';
    const source = safeSource(data.source_url);
    const hostname = source ? new URL(source).hostname : '未知来源';
    $('source-badge').textContent = `官方 ${officialCount} · 平台 ${data.models.length - officialCount}` + (staleCount ? ` · 待复核 ${staleCount}` : '');
    $('scope-note').textContent = '优先展示已核对的官方规格；官方未列字段保持空缺，未核实型号明确标为平台规格。官方 API、开源权重与聚合平台的上限可能不同，点击模型查看对照与证据。';
    render();
  } catch (error) {
    $('status').textContent = ''; $('error').hidden = false;
    $('updated').textContent = '读取失败';
    $('error-message').textContent = location.protocol === 'file:'
      ? '请通过 HTTP 服务或 GitHub Pages 打开此页面；浏览器不允许直接读取本地 JSON 文件。'
      : `读取 data/models.json 失败（${error.message}）。请稍后重试，或通过页面顶部的“原始数据”检查文件。`;
  } finally { $('retry').disabled = false; }
}
$('search').addEventListener('input', render);
$('provider').addEventListener('change', render);
$('sort').addEventListener('change', render);
$('basis').addEventListener('change', () => {
  render();
  if ($('detail').open) {
    const selected = currentModels().find(model => model.id === selectedModelId);
    if (selected) openDetails(selected);
  }
});
$('reset').addEventListener('click', reset); $('empty-reset').addEventListener('click', reset);
$('retry').addEventListener('click', load);
document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
  const key = button.dataset.filter; active.has(key) ? active.delete(key) : active.add(key);
  button.setAttribute('aria-pressed', String(active.has(key))); render();
}));
function closeDetails() {
  $('detail').close();
  document.body.classList.remove('detail-open');
  document.querySelectorAll('#models tr.selected').forEach(row => row.classList.remove('selected'));
  if (detailTrigger?.isConnected) detailTrigger.focus({preventScroll:true});
}
$('close-detail').addEventListener('click', closeDetails);
document.addEventListener('keydown', event => { if (event.key === 'Escape' && $('detail').open) { event.preventDefault(); closeDetails(); } });
load();
