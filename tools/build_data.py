# -*- coding: utf-8 -*-
"""从《产品项目管理表.xlsx》生成网站数据 data/data.js

用法： python tools/build_data.py  [可选的 xlsx 路径]
默认读取 ../../产品项目管理表.xlsx（即“项目管理”目录下），输出 ../data/data.js
"""
import sys, os, re, json, datetime, difflib
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
DEFAULT_XLSX = os.path.join(os.path.dirname(SITE), '产品项目管理表.xlsx')

xlsx = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XLSX
wb = openpyxl.load_workbook(xlsx, data_only=True)


def clean(v):
    if v is None:
        return None
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, str):
        s = v.replace('\u3000', ' ').strip()
        return s or None
    return v


def parse_date(v):
    """把 Excel 日期/中文日期/2026/10/8 统一为 YYYY-MM-DD"""
    if v is None:
        return None
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime('%Y-%m-%d')
    s = str(v).strip()
    m = re.search(r'(\d{4})\s*[年/\-.]\s*(\d{1,2})\s*[月/\-.]\s*(\d{1,2})', s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return '%04d-%02d-%02d' % (y, mo, d)
    m = re.search(r'^(\d{4})\s*年\s*(\d{1,2})\s*月$', s)
    if m:
        return '%04d-%02d-01' % (int(m.group(1)), int(m.group(2)))
    return None


def norm_name(s):
    if not s:
        return ''
    s = re.sub(r'[（(].*?[)）]', '', str(s))
    s = re.sub(r'[\s\-_/、，,。·.]+', '', s)
    return s.lower()


# ---------------- 年度开发 MAP ----------------
ws = wb['年度开发MAP']
month_labels = []
for col in range(2, ws.max_column + 1):
    v = clean(ws.cell(row=2, column=col).value)
    if not v:
        continue
    label = str(v)
    if label.startswith('2027'):
        month_labels.append({'label': '2027.' + label.replace('2027年', '').replace('月', '').zfill(2),
                             'year': 2027, 'short': label.replace('2027年', '')})
    else:
        month_labels.append({'label': '2026.' + str(int(re.sub(r'\D', '', label) or 0)).zfill(2),
                             'year': 2026, 'short': str(label)})

# ---------------- 工作池 ----------------
ws = wb['产品研发工作池']
header = [clean(c.value) for c in ws[1]]
pool = []
for r in ws.iter_rows(min_row=2, values_only=True):
    if not clean(r[3]):
        continue
    pool.append({
        'type': clean(r[0]) or '未分类',
        'status': clean(r[1]) or '',
        'done': clean(r[2]) or '',
        'name': clean(r[3]),
        'must': clean(r[4]) or '',
        'owner': clean(r[5]) or '—',
        'founded': parse_date(r[6]),
        'started': parse_date(r[7]),
        'plan': parse_date(r[8]),
        'actual': parse_date(r[9]),
        'priority': clean(r[10]) or '',
        'phase': clean(r[11]) or '',
        'note': clean(r[13]) or '',
        'isKey': '重点项目' in (clean(r[13]) or ''),
    })
for i, p in enumerate(pool):
    p['id'] = 'p%02d' % i

# ---------------- 重点项目 ----------------
ws = wb['自研重点产品开发进度表']
key = []
for r in ws.iter_rows(min_row=2, values_only=True):
    if not clean(r[3]):
        continue
    key.append({
        'type': clean(r[0]) or '',
        'status': clean(r[1]) or '',
        'done': clean(r[2]) or '',
        'name': clean(r[3]),
        'owner': clean(r[4]) or '—',
        'founded': parse_date(r[5]),
        'started': parse_date(r[6]),
        'plan': parse_date(r[7]),
        'actual': parse_date(r[8]),
        'priority': clean(r[9]) or '',
        'note': clean(r[11]) or '',
        'link': clean(r[12]) or '',
    })
for i, k in enumerate(key):
    k['id'] = 'k%02d' % i

# 以“重点项目表”校准工作池中同名项目的计划时间：
# 重点表通常更新更及时，取两者中较晚的计划日期，并保留原始值以便追溯。
key_by_name = {k['name']: k for k in key}
for p in pool:
    kp = key_by_name.get(p['name'])
    if not kp:
        continue
    if kp.get('plan') and (not p.get('plan') or kp['plan'] > p['plan']):
        change = True
        if p.get('plan'):
            d1 = datetime.date.fromisoformat(p['plan'])
            d2 = datetime.date.fromisoformat(kp['plan'])
            change = (d2 - d1).days > 3
        if change:
            p['planRaw'] = p.get('plan')
            p['plan'] = kp['plan']
            p['reconciled'] = True
    if not p.get('priority') and kp.get('priority'):
        p['priority'] = kp['priority']
        p['reconciled'] = True
    if p.get('done') == '已完成' and not p.get('actual') and kp.get('actual'):
        p['actual'] = kp['actual']

# ---------------- WBS ----------------
ws = wb['重点项目WBS进度表']
proj_order, projects = [], {}
for r in ws.iter_rows(min_row=2, values_only=True):
    if not clean(r[0]) or not clean(r[4]):
        continue
    name = clean(r[0])
    if name not in projects:
        projects[name] = {'name': name, 'priority': clean(r[1]) or '', 'phases': []}
        proj_order.append(name)
    proj = projects[name]
    phase_name = clean(r[2]) or '未分阶段'
    phase = next((p for p in proj['phases'] if p['name'] == phase_name), None)
    if phase is None:
        phase = {'name': phase_name, 'tasks': []}
        proj['phases'].append(phase)
    phase['tasks'].append({
        'seq': str(clean(r[3]) or ''),
        'name': clean(r[4]),
        'status': clean(r[5]) or '正常',
        'done': clean(r[6]) or '未完成',
        'dept': clean(r[7]) or '—',
        'days': r[8] if isinstance(r[8], (int, float)) else None,
        'prev': clean(r[9]) or '',
        'month': clean(r[10]) or '',
        'start': parse_date(r[11]),
        'end': parse_date(r[12]),
        'actual': parse_date(r[13]),
        'milestone': (clean(r[14]) or '') != '',
        'output': clean(r[15]) or '',
        'note': clean(r[16]) or '',
        'taskKey': name + '|' + str(clean(r[3])),
    })

# ---------------- 外协 ----------------
ws = wb['外协产品开发进度表']
outs = []
for i, r in enumerate(ws.iter_rows(min_row=2, values_only=True)):
    if not clean(r[0]):
        continue
    outs.append({
        'id': 'o%02d' % i,
        'name': clean(r[0]),
        'status': clean(r[1]) or '',
        'progress': clean(r[2]) or '',
        'ptype': clean(r[3]) or '',
        'supplier': clean(r[4]) or '—',
        'sample1Date': parse_date(r[5]),
        'sample1': clean(r[6]) or '',
        'result1': clean(r[7]) or '',
        'confirm1Date': parse_date(r[8]),
        'round2': (clean(r[9]) or '') == '✅',
        'sample2Date': parse_date(r[10]),
        'result2': clean(r[11]) or '',
        'adopted': (clean(r[12]) or '') == '✅',
        'adoptDate': parse_date(r[13]),
        'planAdopt': parse_date(r[14]),
    })

# ---------------- 配色 ----------------
ws = wb['产品部配色管理表']
colors = []
for i, r in enumerate(ws.iter_rows(min_row=2, values_only=True)):
    if not clean(r[4]) or not clean(r[6]):
        continue
    colors.append({
        'id': 'c%02d' % i,
        'request': parse_date(r[0]),
        'status': clean(r[1]) or '',
        'done': clean(r[2]) or '',
        'dept': clean(r[3]) or '—',
        'spu': clean(r[4]),
        'ctype': clean(r[5]) or '',
        'color': clean(r[6]),
        'ref': clean(r[7]) or '',
        'due': parse_date(r[8]),
        'trial': clean(r[9]) or '',
        'finish': parse_date(r[10]),
        'note': clean(r[12]) or '',
    })

# ---------------- MAP 状态推导 ----------------
pool_by_norm = {}
for p in pool:
    pool_by_norm[norm_name(p['name'])] = p
norm_keys = list(pool_by_norm.keys())


def match_pool(text):
    t = norm_name(text)
    if not t:
        return None
    if t in pool_by_norm:
        return pool_by_norm[t]
    # 包含关系
    cands = [k for k in norm_keys if k and (k in t or t in k)
             and min(len(k), len(t)) >= 4
             and min(len(k), len(t)) / max(len(k), len(t)) >= 0.55]
    if cands:
        best = max(cands, key=lambda k: min(len(k), len(t)))
        return pool_by_norm[best]
    close = difflib.get_close_matches(t, norm_keys, n=1, cutoff=0.84)
    if close:
        return pool_by_norm[close[0]]
    return None


ws = wb['年度开发MAP']
groups = []
current_type = None
for row in range(3, ws.max_row + 1):
    a = clean(ws.cell(row=row, column=1).value)
    if a:
        current_type = a
        groups.append({'type': a, 'items': []})
    if not current_type:
        continue
    for col in range(2, 2 + len(month_labels)):
        v = clean(ws.cell(row=row, column=col).value)
        if not v:
            continue
        status, matched = 'active', None
        if str(v).startswith('*延期'):
            status = 'delay'
        else:
            matched = match_pool(v)
            if matched:
                if matched['status'] == '暂停':
                    status = 'paused'
                elif matched['status'] == '取消':
                    status = 'cancel'
                elif matched['done'] == '已完成':
                    status = 'done'
                elif matched['status'] == '未开展':
                    status = 'planned'
        groups[-1]['items'].append({
            'text': re.sub(r'^\*延期[—\-]?', '', str(v)),
            'raw': str(v),
            'col': col - 2,
            'status': status,
            'match': matched['name'] if matched else None,
        })

map_groups = [g for g in groups if g['items']]

data = {
    'meta': {
        'source': os.path.basename(xlsx),
        'snapshot': datetime.date.today().strftime('%Y-%m-%d'),
        'months': month_labels,
        'mapTitle': clean(ws.cell(row=1, column=1).value),
    },
    'map': map_groups,
    'pool': pool,
    'keyProjects': key,
    'outsourcing': outs,
    'colors': colors,
    'wbs': [projects[n] for n in proj_order],
}

os.makedirs(os.path.join(SITE, 'data'), exist_ok=True)
out = os.path.join(SITE, 'data', 'data.js')
with open(out, 'w', encoding='utf-8') as fh:
    fh.write('/* 由 tools/build_data.py 从 Excel 自动生成，请勿手工修改 */\n')
    fh.write('window.PM_DATA = ')
    json.dump(data, fh, ensure_ascii=False, separators=(',', ':'))
    fh.write(';\n')
print('written', out, 'pool', len(pool), 'key', len(key), 'wbs', len(data['wbs']), 'outs', len(outs), 'colors', len(colors))
