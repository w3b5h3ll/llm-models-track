'use strict';
(() => {
const $ = (id) => document.getElementById('d-' + id);
const PROVIDERS = {
  openrouter: ['OpenRouter', 'O', '#347c67', '#eaf4ef'],
  siliconflow: ['硅基流动', '硅', '#7651c8', '#f2edfc'],
  deepseek: ['DeepSeek', 'D', '#3f64d6', '#edf2ff'],
  moonshot: ['Moonshot AI', 'K', '#333f55', '#eef0f5'],
  aliyun: ['阿里云百炼', '阿', '#ff6a00', '#fff3e8'],
  baidu: ['百度千帆', '百', '#2932e1', '#eef1ff'],
  tencent: ['腾讯混元', '腾', '#0052d9', '#eaf0ff'],
  'z-ai': ['Z.ai', 'Z', '#415bc1', '#eef1fc'],
  anthropic: ['Anthropic', 'A', '#985f40', '#f7eee8'],
  openai: ['OpenAI', 'O', '#347c67', '#eaf4ef'],
  qwen: ['Qwen', 'Q', '#7651c8', '#f2edfc'],
  'x-ai': ['xAI', 'x', '#374155', '#edf0f4'],
};
const KINDS = {free_tier: '免费额度', free_model: '免费模型', discount: '折扣', limited_time_free: '限时免费', credits: '赠送额度'};
const STATUS = {active: '进行中', stale: '待复核', expired: '已结束'};
let data = null;
let selectedDealId = null;
let detailTrigger = null;
const active = new Set(['active']);
const datetime = new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false});
const dateOnly = new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit'});
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function safeUrl(url) {
  try { const parsed = new URL(url); return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : null; }
  catch { return null; }
}
function providerOf(deal) { return PROVIDERS[deal.provider] || [deal.provider, deal.provider.slice(0, 1).toUpperCase(), '#475570', '#eef1f7']; }
function deadlineText(deal) {
  if (!deal.ends_at) return '未公布';
  const days = Math.ceil((new Date(deal.ends_at + 'T23:59:59+08:00') - Date.now()) / 86400000);
  if (days < 0) return `${dateOnly.format(new Date(deal.ends_at))} 已过`;
  if (days <= 7) return `${dateOnly.format(new Date(deal.ends_at))} · 剩 ${days} 天`;
  return dateOnly.format(new Date(deal.ends_at));
}
function verifiedText(deal) {
  const date = new Date(deal.verified_at);
  return Number.isNaN(date.getTime()) ? '未知' : datetime.format(date).replace(', ', ' ');
}
function currentDeals() {
  return data.deals.filter(deal => {
    if (!active.has(deal.status)) return false;
    const query = $('search').value.trim().toLowerCase();
    if ($('provider').value && deal.provider !== $('provider').value) return false;
    if ($('kind').value && deal.kind !== $('kind').value) return false;
    const haystack = `${deal.title} ${deal.provider} ${deal.reward} ${deal.eligibility} ${deal.claim_steps} ${KINDS[deal.kind] || ''}`;
    if (query && !haystack.toLowerCase().includes(query)) return false;
    return true;
  });
}
function render() {
  if (!data) return;
  const deals = currentDeals();
  const sort = $('sort').value;
  deals.sort((a, b) => {
    if (sort === 'provider') return a.provider.localeCompare(b.provider) || a.title.localeCompare(b.title, 'zh');
    if (sort === 'verified') return (b.verified_at || '').localeCompare(a.verified_at || '');
    const aEnd = a.ends_at || '9999-12-31', bEnd = b.ends_at || '9999-12-31';
    return aEnd.localeCompare(bEnd) || a.title.localeCompare(b.title, 'zh');
  });
  $('deals').replaceChildren();
  $('result-count').textContent = `${deals.length} / ${data.deals.length}`;
  $('status').textContent = `显示 ${deals.length} 个活动，共 ${data.deals.length} 个`;
  $('empty').hidden = deals.length !== 0;
  for (const deal of deals) {
    const tr = element('tr');
    tr.dataset.dealId = deal.id;
    tr.classList.toggle('selected', deal.id === selectedDealId && $('detail').open);
    const td = element('td');
    const identity = element('div', 'model-cell');
    const [name, monogram, color, tint] = providerOf(deal);
    const avatar = element('span', 'avatar', monogram);
    avatar.setAttribute('aria-hidden', 'true'); avatar.style.setProperty('--color', color); avatar.style.setProperty('--tint', tint);
    const text = element('div');
    const button = element('button', 'model-button', deal.title);
    button.type = 'button'; button.addEventListener('click', () => openDetails(deal));
    const providerLine = element('div', 'provider-name', name);
    providerLine.append(element('span', 'kind-tag', KINDS[deal.kind] || deal.kind));
    text.append(button, providerLine); identity.append(avatar, text); td.append(identity); tr.append(td);
    const reward = element('td', 'reward-cell', deal.reward || '见来源页面');
    reward.title = deal.reward || '';
    tr.append(reward);
    tr.append(element('td', '', deal.eligibility || '见来源页面'));
    const deadline = element('td', 'deadline', deadlineText(deal));
    if (deal.ends_at && new Date(deal.ends_at + 'T23:59:59+08:00') > Date.now() && Math.ceil((new Date(deal.ends_at + 'T23:59:59+08:00') - Date.now()) / 86400000) <= 7) deadline.classList.add('soon');
    tr.append(deadline);
    const statusCell = element('td');
    statusCell.append(element('span', 'status-badge ' + deal.status, STATUS[deal.status] || deal.status));
    if (deal.note) statusCell.append(element('div', 'status-note', deal.note));
    tr.append(statusCell);
    tr.append(element('td', 'verified-cell', verifiedText(deal)));
    $('deals').append(tr);
  }
}
function openDetails(deal) {
  selectedDealId = deal.id;
  detailTrigger = document.activeElement;
  document.body.classList.add('detail-open');
  document.querySelectorAll('#d-deals tr').forEach(row => row.classList.toggle('selected', row.dataset.dealId === deal.id));
  $('detail-title').textContent = deal.title;
  $('detail-provider').textContent = (PROVIDERS[deal.provider] || [deal.provider])[0] + ' · ' + deal.id;
  const fields = [
    ['类型', KINDS[deal.kind] || deal.kind], ['权益', deal.reward || '见来源页面'],
    ['领取方式', deal.claim_steps || '见来源页面'], ['适用对象', deal.eligibility || '见来源页面'],
    ['截止', deadlineText(deal)], ['状态', STATUS[deal.status] || deal.status],
    ['最近核实', verifiedText(deal)],
  ];
  if (deal.note) fields.push(['核实备注', deal.note]);
  $('detail-fields').replaceChildren();
  for (const [key, value] of fields) $('detail-fields').append(element('dt', '', key), element('dd', '', value));
  $('detail-evidence').replaceChildren();
  const evidence = deal.evidence || {};
  if (evidence.quote) {
    const block = element('div', 'evidence-item');
    block.append(element('strong', '', '收录时的官方原文'), element('blockquote', '', evidence.quote));
    $('detail-evidence').append(block);
  } else $('evidence-panel').hidden = true;
  $('evidence-panel').hidden = !evidence.quote;
  $('evidence-panel').open = false;
  const url = safeUrl(evidence.url || deal.claim_url);
  $('detail-source').hidden = !url;
  if (url) $('detail-source').href = url;
  if (!$('detail').open) $('detail').show();
}
function updateStats() {
  const deals = data.deals;
  $('active-count').textContent = deals.filter(d => d.status === 'active').length;
  $('provider-count').textContent = new Set(deals.filter(d => d.status === 'active').map(d => d.provider)).size;
  $('stale-count').textContent = deals.filter(d => d.status === 'stale').length;
  $('candidate-count').textContent = (data.pending || []).length;
  const stale = deals.filter(d => d.status === 'stale').length;
  $('verify-badge').textContent = `进行中 ${deals.filter(d => d.status === 'active').length}` + (stale ? ` · 待复核 ${stale}` : '') + (deals.some(d => d.status === 'expired') ? ` · 已结束 ${deals.filter(d => d.status === 'expired').length}` : '');
}
function renderPending() {
  const pending = data.pending || [];
  $('pending-section').hidden = !pending.length;
  if (!pending.length) return;
  $('pending-badge').textContent = pending.length;
  $('pending-list').replaceChildren();
  for (const item of pending) {
    const li = element('li', 'pending-item');
    const head = element('div', 'pending-head');
    const [name, monogram, color, tint] = providerOf(item);
    const avatar = element('span', 'avatar', monogram);
    avatar.setAttribute('aria-hidden', 'true'); avatar.style.setProperty('--color', color); avatar.style.setProperty('--tint', tint);
    const text = element('div');
    text.append(element('strong', '', item.title));
    const meta = element('div', 'provider-name', name);
    meta.append(element('span', 'kind-tag', KINDS[item.kind] || item.kind || '待归类'));
    text.append(meta);
    head.append(avatar, text);
    li.append(head);
    if (item.reward) li.append(element('p', 'pending-reward', item.reward));
    const quote = element('blockquote', '', item.evidence?.quote || '');
    li.append(quote);
    const href = safeUrl(item.evidence?.url || item.claim_url);
    if (href) {
      const link = element('a', '', '来源页面 ↗');
      link.href = href; link.target = '_blank'; link.rel = 'noopener noreferrer';
      li.append(link);
    }
    $('pending-list').append(li);
  }
}
function reset() {
  $('search').value = ''; $('provider').value = ''; $('kind').value = ''; $('sort').value = 'deadline';
  active.clear(); active.add('active');
  document.querySelectorAll('#view-deals [data-filter]').forEach(button => button.setAttribute('aria-pressed', String(active.has(button.dataset.filter))));
  render();
}
async function load() {
  $('error').hidden = true; $('retry').disabled = true;
  $('status').classList.remove('sr-only'); $('status').textContent = '正在读取活动数据…';
  try {
    const response = await fetch('data/deals.json', {cache: 'no-cache'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const incoming = await response.json();
    if (!Array.isArray(incoming.deals) || !incoming.deals.every(d => d && typeof d.id === 'string' && typeof d.title === 'string' && d.evidence)) throw new Error('活动数据格式不正确');
    data = incoming;
    const providers = [...new Set(data.deals.map(d => d.provider))].sort();
    $('provider').replaceChildren(new Option('全部平台', ''));
    providers.forEach(p => $('provider').append(new Option((PROVIDERS[p] || [p])[0], p)));
    const kinds = [...new Set(data.deals.map(d => d.kind))].sort();
    $('kind').replaceChildren(new Option('全部类型', ''));
    kinds.forEach(kind => $('kind').append(new Option(KINDS[kind] || kind, kind)));
    const date = new Date(data.checked_at);
    $('checked').textContent = Number.isNaN(date.getTime()) ? '未知' : datetime.format(date).replace(', ', ' ') + ' 北京时间';
    if (!Number.isNaN(date.getTime())) $('checked').dateTime = date.toISOString();
    const pending = data.pending || [];
    $('pending-count').textContent = pending.length ? `新发现候选 ${pending.length} 条，待人工确认` : '暂无新发现候选';
    updateStats();
    render();
    renderPending();
  } catch (error) {
    $('status').textContent = ''; $('error').hidden = false;
    $('checked').textContent = '读取失败';
    $('error-message').textContent = location.protocol === 'file:'
      ? '请通过 HTTP 服务或 GitHub Pages 打开此页面；浏览器不允许直接读取本地 JSON 文件。'
      : `读取 data/deals.json 失败（${error.message}）。请稍后重试。`;
  } finally { $('retry').disabled = false; }
}
$('search').addEventListener('input', render);
$('provider').addEventListener('change', render);
$('kind').addEventListener('change', render);
$('sort').addEventListener('change', render);
$('reset').addEventListener('click', reset); $('empty-reset').addEventListener('click', reset);
$('retry').addEventListener('click', load);
document.querySelectorAll('#view-deals [data-filter]').forEach(button => button.addEventListener('click', () => {
  const key = button.dataset.filter;
  active.has(key) ? active.delete(key) : active.add(key);
  button.setAttribute('aria-pressed', String(active.has(key))); render();
}));
function closeDetails() {
  $('detail').close();
  document.body.classList.remove('detail-open');
  document.querySelectorAll('#d-deals tr.selected').forEach(row => row.classList.remove('selected'));
  if (detailTrigger?.isConnected) detailTrigger.focus({preventScroll: true});
}
$('close-detail').addEventListener('click', closeDetails);
document.addEventListener('keydown', event => { if (event.key === 'Escape' && $('detail').open) { event.preventDefault(); closeDetails(); } });
load();
})();
