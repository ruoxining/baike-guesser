"""Tag ngram JSON files with domain and entity labels.

Reads {n}gram.json from the corpus directory and writes {n}gram_tags.json
alongside it.  No external dependencies required.

Tag format (sparse — only non-null tags are stored):
  {ngram: {"domain": str, "is_entity": bool}}

Domains (预设领域):
  文学  史学  哲学  数学  物理  化学  生物  地理  人物
  政治  经济  体育  艺术  医学  科技

Entity definition: ngram refers to a specific named thing (proper noun).
Concept definition: ngram refers to a general idea, process, or category.

Usage:
  python scripts/tag_ngrams.py [--corpus google-ngram-zh]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Domain seed substrings.
# A ngram is assigned the first domain whose seed list contains a substring
# that appears inside the ngram.  Seeds are checked longest-first to avoid
# short seeds masking longer, more specific ones.
# ---------------------------------------------------------------------------
_DOMAIN_SEEDS: dict[str, list[str]] = {
    '物理': [
        '量子', '粒子', '原子核', '中子', '质子', '电子', '光子', '引力', '动量',
        '磁场', '电场', '波长', '频率', '辐射', '能量', '熵', '热力学',
        '力学', '光学', '声学', '电磁', '核物理',
    ],
    '化学': [
        '有机化', '无机化', '化合物', '元素周期', '原子量', '分子量',
        '氧化', '还原', '酸碱', '催化剂', '电解', '聚合物',
        '烷烃', '烯烃', '苯环', '氨基酸', '化学键',
        '氢键', '离子键', '共价键',
    ],
    '生物': [
        '细胞', '基因', '染色体', '蛋白质', '酶', '核酸', 'DNA', 'RNA',
        '进化论', '遗传', '免疫', '微生物', '病毒', '细菌', '真菌',
        '光合作用', '呼吸作用', '生态系统', '种群', '群落',
        '哺乳', '爬行', '两栖', '鱼类', '昆虫', '植物界',
    ],
    '数学': [
        '方程', '函数', '集合论', '矩阵', '行列式', '向量空间',
        '积分', '微分', '极限', '级数', '拓扑', '群论',
        '数论', '代数', '几何学', '概率论', '统计学',
        '欧几里得', '勾股', '素数', '无穷',
    ],
    '哲学': [
        '形而上', '本体论', '认识论', '伦理学', '逻辑学',
        '辩证法', '唯物', '唯心', '实证主义', '存在主义',
        '现象学', '结构主义', '后现代', '儒家', '道家', '佛教',
        '孔子', '老子', '庄子', '墨子', '孟子', '荀子',
        '柏拉图', '亚里士多德', '康德', '黑格尔', '尼采',
    ],
    '文学': [
        '诗歌', '散文', '小说', '戏剧', '文学', '诗集', '词集',
        '文言文', '白话文', '古典文学', '现代文学', '当代文学',
        '唐诗', '宋词', '元曲', '明清小说',
        '鲁迅', '巴金', '茅盾', '老舍', '曹雪芹', '吴承恩',
        '莎士比亚', '托尔斯泰', '雨果', '巴尔扎克',
    ],
    '史学': [
        '王朝', '帝国', '历史', '史记', '资治通鉴', '二十四史',
        '战役', '起义', '革命', '改革', '条约', '协议', '宣言',
        '奴隶制', '封建', '资本主义', '社会主义',
        '原始社会', '古代史', '近代史', '现代史',
        '考古', '文物', '遗址', '出土',
    ],
    '地理': [
        '大陆', '半岛', '海峡', '海湾', '群岛', '盆地', '高原', '平原',
        '山脉', '山峰', '河流', '湖泊', '沙漠', '草原', '森林',
        '气候', '地形', '地貌', '地质', '板块', '地震', '火山',
        '经纬度', '时区', '赤道', '极地',
    ],
    '人物': [
        '皇帝', '国王', '总统', '首相', '将军', '元帅',
        '科学家', '物理学家', '化学家', '生物学家', '数学家',
        '哲学家', '文学家', '历史学家', '政治家', '外交家',
        '发明家', '探险家', '艺术家', '音乐家', '画家',
    ],
    '政治': [
        '宪法', '议会', '民主制', '共和制', '联邦', '政党',
        '选举制', '立法', '司法', '行政', '政治学',
        '主权', '法治', '三权分立', '政治体制', '执政党',
        '国际关系', '外交政策', '联合国', '人权',
    ],
    '经济': [
        '经济学', '货币', '通货膨胀', '失业率', '贸易',
        '关税', '金融危机', '资本市场', '证券', '债券',
        '股票市场', '汇率', '宏观经济', '微观经济',
        '供求关系', '市场经济', '计划经济', '自由贸易',
        '国内生产总值', '经济增长',
    ],
    '体育': [
        '奥运会', '世界杯', '运动会', '锦标赛', '联赛',
        '冠军赛', '田径', '游泳', '足球', '篮球',
        '网球', '排球', '乒乓球', '羽毛球', '体育',
        '运动员', '马拉松', '铁人三项', '体操',
    ],
    '艺术': [
        '绘画', '雕塑', '交响乐', '歌剧', '舞蹈',
        '书法', '陶瓷', '建筑艺术', '摄影', '电影',
        '戏曲', '芭蕾', '作曲家', '指挥家', '美术',
        '油画', '水墨', '版画', '古典音乐',
    ],
    '医学': [
        '医学', '外科', '内科', '病理', '解剖',
        '药理', '疾病', '临床', '中医学', '西医',
        '针灸', '诊断', '症状', '手术', '治疗方',
        '药物学', '流行病', '公共卫生',
    ],
    '科技': [
        '计算机', '互联网', '人工智能', '软件', '算法',
        '网络协议', '数据库', '半导体', '航天', '航空',
        '工程学', '机械', '电气', '通信', '卫星',
        '芯片', '信息技术', '自动化', '机器人',
    ],
}

# Flatten and sort seeds longest-first within each domain to avoid prefix collisions
_SORTED_SEEDS: list[tuple[str, str]] = []
for _domain, _seeds in _DOMAIN_SEEDS.items():
    for _seed in _seeds:
        _SORTED_SEEDS.append((_seed, _domain))
_SORTED_SEEDS.sort(key=lambda x: -len(x[0]))


# ---------------------------------------------------------------------------
# Entity detection patterns.
# ---------------------------------------------------------------------------

# Suffixes strongly indicative of named entities
_ENTITY_SUFFIX = re.compile(
    r'(国|省|市|县|区|镇|乡|村'          # administrative divisions
    r'|洲|岛|群岛|半岛|海峡|湾|角'       # geographic
    r'|山|山脉|峰|岭|岳|丘'             # landforms
    r'|河|江|湖|海|洋|泊|溪|泉'         # water bodies
    r'|朝|王朝|帝国|王国'               # historical states
    r'|大学|学院|学校|研究院|研究所|实验室'    # institutions
    r'|党|军|会|社|组织|联盟|协会|委员会'     # organizations
    r'|战役|之战|会战|之乱|之变|起义'     # battles and uprisings
    r'|条约|协议|宣言|公约'              # documents
    r'|本纪|列传|世家'                  # historical chronicle sections
    r'|斯坦|尼亚|利亚|维亚|伊亚|格勒'    # foreign place transliterations
    r'|天皇|大帝|大汗)$'               # historical rulers
)

# Prefixes strongly indicative of named entities (dynasties, countries, etc.)
_ENTITY_PREFIX = re.compile(
    r'^(中华|中国|美国|英国|法国|德国|日本|俄国|苏联|韩国|朝鲜'
    r'|唐|宋|元|明|清|汉|周|秦|隋|晋|魏|吴|蜀'
    r'|古埃及|古罗马|古希腊|拜占庭|奥斯曼'
    r'|波斯|印度|蒙古|波兰|奥地利|普鲁士|荷兰'
    r'|阿拉伯|土耳其|越南|菲律宾|印尼|马来)'
)

# ---------------------------------------------------------------------------
# Person name heuristic.
# Surnames that appear almost exclusively as surnames in modern written Chinese,
# minimising false matches with common morphemes.
# ---------------------------------------------------------------------------
_PERSON_SURNAMES = frozenset(
    '赵邓蔡彭潘廖姚戴崔邱谭薛郝邵龚辛阮管岳涂游温'
    '莫霍乔巩卜费项岑'
    # Surnames also common as morpheme heads are intentionally excluded
    # (王/李/张/陈/杨/方/金/程/任/万/林/刘/吴/胡/等)
)

# Characters that strongly indicate a non-name compound when present anywhere
# in a candidate ngram.  Excludes size/positional chars (大小中上下) since
# those do appear in Chinese given names (e.g. 邓小平, 陈大明).
_NAME_STOP_CHARS = frozenset(
    '的是在有年了被和也都不为以而其由于与月日后前此该将已曾可得使'
    '们这那个各很就都些从到对'
)


def detect_domain(ngram: str) -> str | None:
    for seed, domain in _SORTED_SEEDS:
        if seed in ngram:
            return domain
    return None


def detect_entity(ngram: str, n: int) -> bool:
    if n <= 1:
        return False
    if _ENTITY_SUFFIX.search(ngram):
        return True
    if _ENTITY_PREFIX.match(ngram):
        return True
    return False


def detect_person_name(ngram: str, n: int) -> bool:
    """Heuristic: length 2-4, starts with a distinctive surname, no stop chars."""
    if n < 2 or n > 4:
        return False
    if ngram[0] not in _PERSON_SURNAMES:
        return False
    if any(c in _NAME_STOP_CHARS for c in ngram):
        return False
    return True


def tag_corpus(corpus_dir: Path) -> None:
    for n in range(1, 7):
        json_path = corpus_dir / f'{n}gram.json'
        if not json_path.exists():
            print(f'  {n}gram.json not found, skipping')
            continue

        with json_path.open('r', encoding='utf-8') as f:
            freqs: dict[str, float] = json.load(f)

        tags: dict[str, dict] = {}
        for ngram in freqs:
            entry: dict = {}
            domain = detect_domain(ngram)
            if domain:
                entry['domain'] = domain
            is_entity = detect_entity(ngram, n) or detect_person_name(ngram, n)
            if is_entity:
                entry['is_entity'] = True
            if entry:
                tags[ngram] = entry

        out_path = corpus_dir / f'{n}gram_tags.json'
        with out_path.open('w', encoding='utf-8') as f:
            json.dump(tags, f, ensure_ascii=False)

        n_entity = sum(1 for v in tags.values() if v.get('is_entity'))
        n_domain = sum(1 for v in tags.values() if v.get('domain'))
        pct = 100 * len(tags) / max(len(freqs), 1)
        print(f'  {n}gram: {len(freqs):>8,} ngrams → {len(tags):>7,} tagged ({pct:.1f}%)  '
              f'entity={n_entity:,}  domain={n_domain:,}')

    print('done.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', default='google-ngram-zh',
                        help='path to corpus directory containing {n}gram.json files')
    args = parser.parse_args()
    corpus_dir = Path(args.corpus)
    print(f'tagging {corpus_dir} ...')
    tag_corpus(corpus_dir)
