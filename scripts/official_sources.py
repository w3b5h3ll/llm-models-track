"""Verified official documentation adapters. Never fill official gaps with relay data."""
import concurrent.futures
import copy
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

FIELDS = ('context_tokens', 'max_input_tokens', 'max_output_tokens',
          'input_modalities', 'output_modalities', 'tool_call', 'reasoning',
          'max_input_tokens_thinking', 'max_input_tokens_non_thinking', 'context_extended_tokens')


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if not self.skip and tag in ('p', 'h1', 'h2', 'h3', 'div', 'tr', 'li', 'br'):
            self.parts.append('\n')
        if not self.skip and tag in ('td', 'th'):
            self.parts.append(' | ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, value):
        if not self.skip:
            self.parts.append(value)


def page_text(raw):
    if '<html' not in raw.lower():
        return raw
    parser = PageText()
    parser.feed(raw)
    return '\n'.join(re.sub(r'\s+', ' ', line).strip()
                     for line in ''.join(parser.parts).splitlines() if line.strip())


def fetch_page(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Model-Watch; documentation sync)'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return page_text(response.read().decode('utf-8'))


def token_count(raw):
    match = re.fullmatch(r'([\d,]+(?:\.\d+)?)\s*([KM]?)', raw.strip(), re.I)
    if not match:
        raise ValueError(f'无法解析 token 数值：{raw}')
    # Preserve the publisher's original shorthand. Decimal expansion is for sorting only.
    return int(float(match[1].replace(',', '')) * {'': 1, 'K': 1000, 'M': 1000000}[match[2].upper()])


def parse_rule(rule, text):
    for required in rule.get('requires', []):
        if not re.search(required, text, re.I | re.M):
            raise ValueError('官方页面身份或结构校验失败')
    values = dict.fromkeys(FIELDS)
    evidence = {}
    if rule.get('kind') == 'claude_table':
        def row(name):
            match = re.search(r'^\| ' + re.escape(name) + r' \| (.+)$', text, re.M)
            if not match:
                raise ValueError('Claude 参数表结构发生变化')
            return [part.strip() for part in match[1].split('|')]
        ids = row('Claude API ID')
        index = ids.index(rule['official_model_id'])
        for field, label in [('context_tokens', 'Context window'), ('max_output_tokens', 'Max output')]:
            cell = row(label)[index]
            reported = cell.removesuffix(' tokens').strip()
            values[field] = token_count(reported)
            evidence[field] = {'url': rule['url'], 'quote': f'{rule["official_model_id"]}: {label} = {cell}', 'reported': reported}
        thinking = row('Thinking')[index]
        if 'Adaptive' not in thinking and 'Extended' not in thinking:
            raise ValueError('Claude thinking 声明发生变化')
        values['reasoning'] = True
        evidence['reasoning'] = {'url': rule['url'], 'quote': f'{rule["official_model_id"]}: Thinking = {thinking}'}
    for field, extraction in rule.get('fields', {}).items():
        if field not in FIELDS:
            raise ValueError('未知官方字段')
        matches = list(re.finditer(extraction['pattern'], text, re.I | re.M))
        if not matches:
            raise ValueError(f'官方字段解析失败：{field}')
        parsed = []
        for match in matches:
            if extraction.get('type') == 'tokens':
                reported = match.group('value').strip()
                value = token_count(reported)
            else:
                reported = None
                value = extraction['value']
            parsed.append((value, reported, match.group(0)))
        if any(item[0] != parsed[0][0] for item in parsed):
            raise ValueError(f'官方页面存在不同数值，需核对区域/版本：{field}')
        values[field] = parsed[0][0]
        evidence[field] = {'url': rule['url'], 'quote': parsed[0][2][:1200]}
        if parsed[0][1] is not None:
            evidence[field]['reported'] = parsed[0][1]
    if not evidence:
        raise ValueError('未提取到官方规格')
    return {'values': values, 'field_sources': evidence, 'url': rule['url'],
            'official_model_id': rule['official_model_id'], 'scope': rule['scope'],
            'label': rule.get('label', '官方 API')}


def enrich(rows, config, previous=None, loader=fetch_page):
    previous = previous or []
    old = {row['id']: row for row in previous}
    rules = config.get('models', {})
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    urls = {rules[row['id']]['url'] for row in rows if row['id'] in rules}
    pages = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(loader, url): url for url in urls}
        for future in concurrent.futures.as_completed(futures):
            try:
                pages[futures[future]] = future.result()
            except Exception:
                pages[futures[future]] = None
    checks = {'checked_at': now, 'models': {}}
    result = []
    for platform in rows:
        model_id = platform['id']
        row = copy.deepcopy(platform)
        row['platform'] = copy.deepcopy(platform)
        row['basis'] = 'platform'
        row['official'] = None
        rule = rules.get(model_id)
        check = {'status': 'not_configured', 'message': config.get('unverified', {}).get(model_id, '尚未为此型号核对官方规格')}
        if rule:
            previous_official = old.get(model_id, {}).get('official')
            try:
                if pages[rule['url']] is None:
                    raise ValueError('官方页面暂时无法访问')
                spec = parse_rule(rule, pages[rule['url']])
                # Keep evidence update timestamps stable when facts have not changed.
                same = previous_official and all(previous_official.get(k) == v for k, v in spec.items())
                spec['evidence_updated_at'] = previous_official['evidence_updated_at'] if same else now
                spec['status'] = 'verified'
                row['official'] = spec
                check = {'status': 'verified', 'url': rule['url']}
            except (ValueError, TypeError, KeyError, IndexError) as error:
                check = {'status': 'failed', 'url': rule['url'], 'message': str(error)}
                # Only reuse evidence for the same exact model and source mapping.
                if previous_official and previous_official.get('url') == rule['url'] and previous_official.get('official_model_id') == rule['official_model_id']:
                    row['official'] = copy.deepcopy(previous_official)
                    row['official']['status'] = 'stale'
        if row['official']:
            row.update(row['official']['values'])
            row['source'] = row['official']['url']
            row['scope'] = row['official']['scope']
            row['basis'] = 'official'
        row['official_status'] = check['status']
        row['official_note'] = check.get('message', '')
        checks['models'][model_id] = check
        result.append(row)
    return result, checks
