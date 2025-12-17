#!/usr/bin/env python3
"""
SWOT Analyzer CLI — для запуска в GitHub Actions
С поддержкой нативного Anthropic Web Search
"""

import os
import sys
import json
import sqlite3
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import numpy as np
import anthropic

# LangChain
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

# Embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
SIMILARITY_THRESHOLD = 0.8
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SWOTItem:
    text: str
    reasoning: str
    embedding: Optional[List[float]] = None

@dataclass
class StrategicPair:
    factor1: str
    factor2: str
    strategy: str
    risk: Optional[str] = None

@dataclass
class SWOTAnalysis:
    source_file: str
    source_text: str
    context_hash: str
    strengths: List[SWOTItem] = field(default_factory=list)
    weaknesses: List[SWOTItem] = field(default_factory=list)
    opportunities: List[SWOTItem] = field(default_factory=list)
    threats: List[SWOTItem] = field(default_factory=list)
    strategic_so: List[StrategicPair] = field(default_factory=list)
    strategic_wo: List[StrategicPair] = field(default_factory=list)
    strategic_st: List[StrategicPair] = field(default_factory=list)
    strategic_wt: List[StrategicPair] = field(default_factory=list)
    created_at: Optional[str] = None

@dataclass
class ComparisonItem:
    old_text: Optional[str]
    new_text: Optional[str]
    change_type: str
    reasoning: str
    category: str

@dataclass
class SWOTComparison:
    old_id: int
    new_id: int
    items: List[ComparisonItem] = field(default_factory=list)
    summary: str = ""


# =============================================================================
# ПРОМПТЫ
# =============================================================================

SYSTEM_MESSAGE = """Ты — эксперт по стратегическому анализу бизнеса. 
Твоя задача — провести глубокий SWOT-анализ на русском языке.

ВАЖНО:
- S и W — ВНУТРЕННИЕ факторы (то, что компания контролирует)
- O и T — ВНЕШНИЕ факторы (рынок, конкуренты, тренды)
- Каждый пункт должен быть конкретным и обоснованным
- Отвечай ТОЛЬКО валидным JSON без markdown-обёрток"""

PROMPT_SW = """Проанализируй текст и выдели ВНУТРЕННИЕ сильные и слабые стороны.

КОНТЕКСТ КОМПАНИИ:
{context}

ТЕКСТ ДЛЯ АНАЛИЗА:
{text}

Ответь строго в JSON:
{{
    "strengths": [{{"text": "...", "reasoning": "..."}}],
    "weaknesses": [{{"text": "...", "reasoning": "..."}}]
}}

Минимум 5 пунктов в каждой категории."""

PROMPT_OT_SEARCH = """Сформулируй 3-5 поисковых запросов на русском для поиска O и T.

КОНТЕКСТ КОМПАНИИ:
{context}

Ответь в JSON:
{{
    "queries": ["запрос 1", "запрос 2", "запрос 3"]
}}"""

PROMPT_OT = """Выдели ВНЕШНИЕ возможности и угрозы.

КОНТЕКСТ КОМПАНИИ:
{context}

РЕЗУЛЬТАТЫ ИССЛЕДОВАНИЯ РЫНКА:
{search_results}

Ответь в JSON:
{{
    "opportunities": [{{"text": "...", "reasoning": "..."}}],
    "threats": [{{"text": "...", "reasoning": "..."}}]
}}

Минимум 5 пунктов в каждой категории."""

PROMPT_STRATEGIC = """Проведи стратегическое сопоставление SWOT.

STRENGTHS:
{strengths}

WEAKNESSES:
{weaknesses}

OPPORTUNITIES:
{opportunities}

THREATS:
{threats}

Ответь в JSON:
{{
    "so": [{{"factor1": "Сила", "factor2": "Возможность", "strategy": "..."}}],
    "wo": [{{"factor1": "Слабость", "factor2": "Возможность", "strategy": "..."}}],
    "st": [{{"factor1": "Сила", "factor2": "Угроза", "strategy": "..."}}],
    "wt": [{{"factor1": "Слабость", "factor2": "Угроза", "strategy": "...", "risk": "..."}}]
}}

Минимум 3 пары в каждой категории."""

PROMPT_COMPARISON = """Сравни два SWOT-анализа.

ПРЕДЫДУЩИЙ SWOT:
{old_swot}

НОВЫЙ SWOT:
{new_swot}

ПОХОЖИЕ ПАРЫ (similarity > 0.8):
{similar_pairs}

Определи для каждого изменения:
- improved: стало лучше
- worsened: стало хуже  
- lost: исчезло (объясни почему!)
- new: новое

Ответь в JSON:
{{
    "items": [{{
        "old_text": "..." или null,
        "new_text": "..." или null,
        "change_type": "improved|worsened|lost|new",
        "reasoning": "Подробное обоснование",
        "category": "S|W|O|T"
    }}],
    "summary": "Главный вывод"
}}"""


# =============================================================================
# DATABASE
# =============================================================================

def init_db(db_path: Path) -> sqlite3.Connection:
    """Инициализация SQLite"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contexts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            hash TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS swot_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context_id INTEGER,
            source_file TEXT NOT NULL,
            source_text TEXT NOT NULL,
            strengths_json TEXT,
            weaknesses_json TEXT,
            opportunities_json TEXT,
            threats_json TEXT,
            strategic_so_json TEXT,
            strategic_wo_json TEXT,
            strategic_st_json TEXT,
            strategic_wt_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (context_id) REFERENCES contexts(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            old_swot_id INTEGER NOT NULL,
            new_swot_id INTEGER NOT NULL,
            items_json TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    return conn


def get_or_create_context(conn: sqlite3.Connection, content: str) -> int:
    """Получить или создать контекст"""
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM contexts WHERE hash = ?", (content_hash,))
    row = cursor.fetchone()
    
    if row:
        return row[0]
    
    cursor.execute("INSERT INTO contexts (content, hash) VALUES (?, ?)", (content, content_hash))
    conn.commit()
    return cursor.lastrowid


def get_latest_swot(conn: sqlite3.Connection) -> Optional[dict]:
    """Получить последний SWOT"""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM swot_analyses ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    return dict(row) if row else None


def save_swot(conn: sqlite3.Connection, analysis: SWOTAnalysis, context_id: int) -> int:
    """Сохранить SWOT"""
    def to_json(items):
        return json.dumps([asdict(i) for i in items], ensure_ascii=False)
    
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO swot_analyses (
            context_id, source_file, source_text,
            strengths_json, weaknesses_json, opportunities_json, threats_json,
            strategic_so_json, strategic_wo_json, strategic_st_json, strategic_wt_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        context_id, analysis.source_file, analysis.source_text,
        to_json(analysis.strengths), to_json(analysis.weaknesses),
        to_json(analysis.opportunities), to_json(analysis.threats),
        to_json(analysis.strategic_so), to_json(analysis.strategic_wo),
        to_json(analysis.strategic_st), to_json(analysis.strategic_wt)
    ))
    conn.commit()
    return cursor.lastrowid


def load_swot_from_db(swot_dict: dict) -> SWOTAnalysis:
    """Загрузить SWOT из БД"""
    def parse(json_str, cls):
        if not json_str:
            return []
        return [cls(**item) for item in json.loads(json_str)]
    
    return SWOTAnalysis(
        source_file=swot_dict['source_file'],
        source_text=swot_dict['source_text'],
        context_hash="",
        strengths=parse(swot_dict['strengths_json'], SWOTItem),
        weaknesses=parse(swot_dict['weaknesses_json'], SWOTItem),
        opportunities=parse(swot_dict['opportunities_json'], SWOTItem),
        threats=parse(swot_dict['threats_json'], SWOTItem),
        strategic_so=parse(swot_dict['strategic_so_json'], StrategicPair),
        strategic_wo=parse(swot_dict['strategic_wo_json'], StrategicPair),
        strategic_st=parse(swot_dict['strategic_st_json'], StrategicPair),
        strategic_wt=parse(swot_dict['strategic_wt_json'], StrategicPair),
        created_at=swot_dict['created_at']
    )


# =============================================================================
# LLM FUNCTIONS
# =============================================================================

def create_llm():
    """Создать LLM клиент для LangChain"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    return ChatAnthropic(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        anthropic_api_key=api_key
    )


def create_search_client() -> anthropic.Anthropic:
    """Создать клиент Anthropic для веб-поиска"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def parse_json_response(text: str) -> dict:
    """Парсинг JSON из ответа с улучшенной обработкой ошибок"""
    cleaned = text.strip()
    
    # Убираем markdown-обёртки
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    
    cleaned = cleaned.strip()
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Пробуем найти JSON в тексте
        import re
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        print(f"⚠️ Ошибка парсинга JSON: {e}")
        print(f"   Текст: {cleaned[:200]}...")
        raise


def invoke_llm(llm, prompt_template: str, variables: dict, max_retries: int = 2) -> dict:
    """Вызов LLM с ретраями"""
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(SYSTEM_MESSAGE),
        HumanMessagePromptTemplate.from_template(prompt_template)
    ])
    
    chain = prompt | llm
    
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = chain.invoke(variables)
            content = response.content if hasattr(response, 'content') else str(response)
            return parse_json_response(content)
        except json.JSONDecodeError as e:
            last_error = e
            if attempt < max_retries:
                print(f"   🔄 Retry {attempt + 1}/{max_retries}...")
            continue
    
    raise last_error


def invoke_search(client: anthropic.Anthropic, query: str) -> str:
    """Веб-поиск через нативный Anthropic API"""
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search"
            }],
            messages=[{
                "role": "user", 
                "content": f"Найди актуальную информацию по запросу и кратко изложи ключевые факты: {query}"
            }]
        )
        
        # Собираем текст из всех блоков
        result_parts = []
        for block in response.content:
            if hasattr(block, 'text'):
                result_parts.append(block.text)
        
        return "\n".join(result_parts) if result_parts else "Результаты не найдены"
        
    except anthropic.APIError as e:
        print(f"   ⚠️ Ошибка поиска: {e}")
        return f"Ошибка поиска: {str(e)}"


# =============================================================================
# EMBEDDINGS
# =============================================================================

def get_embedding_model():
    """Загрузить модель эмбеддингов"""
    if not EMBEDDINGS_AVAILABLE:
        print("⚠️ sentence-transformers не установлен, сравнение будет без эмбеддингов")
        return None
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def find_similar_pairs(old_texts: list, new_texts: list, model) -> list:
    """Найти похожие пары"""
    if not model or not old_texts or not new_texts:
        return []
    
    old_emb = model.encode(old_texts)
    new_emb = model.encode(new_texts)
    
    pairs = []
    for i, old_txt in enumerate(old_texts):
        best_match = None
        best_score = 0.0
        
        for j, new_txt in enumerate(new_texts):
            score = float(np.dot(old_emb[i], new_emb[j]) / 
                         (np.linalg.norm(old_emb[i]) * np.linalg.norm(new_emb[j])))
            
            if score > best_score and score >= SIMILARITY_THRESHOLD:
                best_score = score
                best_match = (j, new_txt, score)
        
        if best_match:
            pairs.append({
                "old_text": old_txt,
                "new_text": best_match[1],
                "similarity": best_match[2]
            })
    
    return pairs


# =============================================================================
# MAIN ANALYSIS
# =============================================================================

def run_analysis(source_file: Path, context_file: Path, db_path: Path, outputs_dir: Path) -> tuple:
    """Запуск полного анализа"""
    
    print(f"📄 Анализируем: {source_file}")
    
    # Читаем файлы
    source_text = source_file.read_text(encoding='utf-8')
    context_text = context_file.read_text(encoding='utf-8') if context_file.exists() else ""
    
    # Инициализация
    conn = init_db(db_path)
    llm = create_llm()
    search_client = create_search_client()
    
    # Получаем предыдущий SWOT
    prev_dict = get_latest_swot(conn)
    previous_swot = load_swot_from_db(prev_dict) if prev_dict else None
    
    print("📊 Генерация S и W...")
    sw_data = invoke_llm(llm, PROMPT_SW, {"context": context_text, "text": source_text})
    
    strengths = [SWOTItem(text=s["text"], reasoning=s["reasoning"]) for s in sw_data.get("strengths", [])]
    weaknesses = [SWOTItem(text=w["text"], reasoning=w["reasoning"]) for w in sw_data.get("weaknesses", [])]
    print(f"   ✅ S: {len(strengths)}, W: {len(weaknesses)}")
    
    print("🔍 Генерация поисковых запросов...")
    search_data = invoke_llm(llm, PROMPT_OT_SEARCH, {"context": context_text})
    queries = search_data.get("queries", ["тренды рынка"])
    
    print("🌐 Веб-поиск...")
    search_results = []
    for q in queries[:3]:
        print(f"   🔎 {q}")
        result = invoke_search(search_client, q)
        search_results.append(f"Запрос: {q}\nРезультат: {result}\n")
    
    print("📊 Генерация O и T...")
    ot_data = invoke_llm(llm, PROMPT_OT, {"context": context_text, "search_results": "\n".join(search_results)})
    
    opportunities = [SWOTItem(text=o["text"], reasoning=o["reasoning"]) for o in ot_data.get("opportunities", [])]
    threats = [SWOTItem(text=t["text"], reasoning=t["reasoning"]) for t in ot_data.get("threats", [])]
    print(f"   ✅ O: {len(opportunities)}, T: {len(threats)}")
    
    print("🎯 Стратегическое сопоставление...")
    strategic_data = invoke_llm(llm, PROMPT_STRATEGIC, {
        "strengths": "\n".join([f"- {s.text}" for s in strengths]),
        "weaknesses": "\n".join([f"- {w.text}" for w in weaknesses]),
        "opportunities": "\n".join([f"- {o.text}" for o in opportunities]),
        "threats": "\n".join([f"- {t.text}" for t in threats])
    })
    
    def parse_pairs(items, with_risk=False):
        return [StrategicPair(
            factor1=p.get("factor1", ""),
            factor2=p.get("factor2", ""),
            strategy=p.get("strategy", ""),
            risk=p.get("risk") if with_risk else None
        ) for p in items]
    
    strategic_so = parse_pairs(strategic_data.get("so", []))
    strategic_wo = parse_pairs(strategic_data.get("wo", []))
    strategic_st = parse_pairs(strategic_data.get("st", []))
    strategic_wt = parse_pairs(strategic_data.get("wt", []), with_risk=True)
    
    # Создаём объект
    analysis = SWOTAnalysis(
        source_file=source_file.name,
        source_text=source_text,
        context_hash=hashlib.sha256(context_text.encode()).hexdigest()[:16],
        strengths=strengths,
        weaknesses=weaknesses,
        opportunities=opportunities,
        threats=threats,
        strategic_so=strategic_so,
        strategic_wo=strategic_wo,
        strategic_st=strategic_st,
        strategic_wt=strategic_wt
    )
    
    # Сохраняем
    context_id = get_or_create_context(conn, context_text)
    swot_id = save_swot(conn, analysis, context_id)
    print(f"💾 Сохранено: ID={swot_id}")
    
    # Сравнение
    comparison = None
    if previous_swot:
        print("🔄 Сравнение с предыдущим...")
        
        embed_model = get_embedding_model()
        
        old_texts = ([s.text for s in previous_swot.strengths] +
                    [w.text for w in previous_swot.weaknesses] +
                    [o.text for o in previous_swot.opportunities] +
                    [t.text for t in previous_swot.threats])
        
        new_texts = ([s.text for s in strengths] +
                    [w.text for w in weaknesses] +
                    [o.text for o in opportunities] +
                    [t.text for t in threats])
        
        similar_pairs = find_similar_pairs(old_texts, new_texts, embed_model)
        
        comp_data = invoke_llm(llm, PROMPT_COMPARISON, {
            "old_swot": json.dumps({
                "strengths": [s.text for s in previous_swot.strengths],
                "weaknesses": [w.text for w in previous_swot.weaknesses],
                "opportunities": [o.text for o in previous_swot.opportunities],
                "threats": [t.text for t in previous_swot.threats]
            }, ensure_ascii=False),
            "new_swot": json.dumps({
                "strengths": [s.text for s in strengths],
                "weaknesses": [w.text for w in weaknesses],
                "opportunities": [o.text for o in opportunities],
                "threats": [t.text for t in threats]
            }, ensure_ascii=False),
            "similar_pairs": json.dumps(similar_pairs, ensure_ascii=False)
        })
        
        comparison = SWOTComparison(
            old_id=0, new_id=swot_id,
            items=[ComparisonItem(
                old_text=ci.get("old_text"),
                new_text=ci.get("new_text"),
                change_type=ci.get("change_type", ""),
                reasoning=ci.get("reasoning", ""),
                category=ci.get("category", "")
            ) for ci in comp_data.get("items", [])],
            summary=comp_data.get("summary", "")
        )
    
    # Генерация отчётов
    outputs_dir.mkdir(exist_ok=True)
    
    swot_md = generate_swot_markdown(analysis)
    swot_path = outputs_dir / "swot_latest.md"
    swot_path.write_text(swot_md, encoding='utf-8')
    print(f"📄 SWOT: {swot_path}")
    
    comparison_path = None
    if comparison:
        comp_md = generate_comparison_markdown(comparison)
        comparison_path = outputs_dir / "comparison_latest.md"
        comparison_path.write_text(comp_md, encoding='utf-8')
        print(f"📄 Сравнение: {comparison_path}")
    
    conn.close()
    print("✅ Готово!")
    
    return analysis, comparison, swot_path, comparison_path


# =============================================================================
# MARKDOWN GENERATION
# =============================================================================

def generate_swot_markdown(analysis: SWOTAnalysis) -> str:
    """Генерация SWOT в Markdown"""
    
    md = f"""# SWOT-анализ: {analysis.source_file}

**Дата:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

## Strengths (Сильные стороны)

| № | Пункт | Обоснование |
|---|-------|-------------|
"""
    for idx, s in enumerate(analysis.strengths, 1):
        md += f"| {idx} | {s.text} | {s.reasoning} |\n"
    
    md += """
## Weaknesses (Слабые стороны)

| № | Пункт | Обоснование |
|---|-------|-------------|
"""
    for idx, w in enumerate(analysis.weaknesses, 1):
        md += f"| {idx} | {w.text} | {w.reasoning} |\n"
    
    md += """
## Opportunities (Возможности)

| № | Пункт | Обоснование |
|---|-------|-------------|
"""
    for idx, o in enumerate(analysis.opportunities, 1):
        md += f"| {idx} | {o.text} | {o.reasoning} |\n"
    
    md += """
## Threats (Угрозы)

| № | Пункт | Обоснование |
|---|-------|-------------|
"""
    for idx, t in enumerate(analysis.threats, 1):
        md += f"| {idx} | {t.text} | {t.reasoning} |\n"
    
    md += """
---

## Стратегическое сопоставление

### S+O (Наступательная стратегия)

| Сила | Возможность | Стратегия |
|------|-------------|-----------|
"""
    for pair in analysis.strategic_so:
        md += f"| {pair.factor1} | {pair.factor2} | {pair.strategy} |\n"
    
    md += """
### W+O (Стратегия улучшений)

| Слабость | Возможность | Стратегия |
|----------|-------------|-----------|
"""
    for pair in analysis.strategic_wo:
        md += f"| {pair.factor1} | {pair.factor2} | {pair.strategy} |\n"
    
    md += """
### S+T (Защитная стратегия)

| Сила | Угроза | Стратегия |
|------|--------|-----------|
"""
    for pair in analysis.strategic_st:
        md += f"| {pair.factor1} | {pair.factor2} | {pair.strategy} |\n"
    
    md += """
### W+T (Минимизация рисков)

| Слабость | Угроза | Риск | Стратегия |
|----------|--------|------|-----------|
"""
    for pair in analysis.strategic_wt:
        md += f"| {pair.factor1} | {pair.factor2} | {pair.risk or '-'} | {pair.strategy} |\n"
    
    return md


def generate_comparison_markdown(comparison: SWOTComparison) -> str:
    """Генерация сравнения в Markdown"""
    
    md = f"""# Сравнение SWOT-анализов

**Дата:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

## Главный вывод

{comparison.summary}

---

## Детали изменений

"""
    for change_type, emoji, title in [
        ("improved", "✅", "Улучшилось"),
        ("new", "🆕", "Новое"),
        ("worsened", "⚠️", "Ухудшилось"),
        ("lost", "❌", "Потеряно")
    ]:
        filtered = [item for item in comparison.items if item.change_type == change_type]
        if filtered:
            md += f"### {emoji} {title}\n\n"
            md += "| Категория | Было | Стало | Обоснование |\n"
            md += "|-----------|------|-------|-------------|\n"
            for item in filtered:
                md += f"| {item.category} | {item.old_text or '-'} | {item.new_text or '-'} | {item.reasoning} |\n"
            md += "\n"
    
    return md


def generate_pr_comment(analysis: SWOTAnalysis, comparison: Optional[SWOTComparison]) -> str:
    """Генерация комментария для PR"""
    
    comment = f"""## 🎯 SWOT-анализ: `{analysis.source_file}`

### 📊 Результат

| Категория | Кол-во |
|-----------|--------|
| 💪 Strengths | {len(analysis.strengths)} |
| 😰 Weaknesses | {len(analysis.weaknesses)} |
| 🚀 Opportunities | {len(analysis.opportunities)} |
| ⚠️ Threats | {len(analysis.threats)} |

<details>
<summary>📋 Strengths</summary>

"""
    for s in analysis.strengths:
        comment += f"- **{s.text}**\n"
    
    comment += """
</details>

<details>
<summary>📋 Weaknesses</summary>

"""
    for w in analysis.weaknesses:
        comment += f"- **{w.text}**\n"
    
    comment += """
</details>

<details>
<summary>📋 Opportunities</summary>

"""
    for o in analysis.opportunities:
        comment += f"- **{o.text}**\n"
    
    comment += """
</details>

<details>
<summary>📋 Threats</summary>

"""
    for t in analysis.threats:
        comment += f"- **{t.text}**\n"
    
    comment += """
</details>

"""
    
    if comparison and comparison.items:
        improved = len([c for c in comparison.items if c.change_type == "improved"])
        worsened = len([c for c in comparison.items if c.change_type == "worsened"])
        lost = len([c for c in comparison.items if c.change_type == "lost"])
        new_count = len([c for c in comparison.items if c.change_type == "new"])
        
        comment += f"""
---

### 🔄 Сравнение с предыдущим

| Изменение | Кол-во |
|-----------|--------|
| ✅ Улучшилось | {improved} |
| 🆕 Новое | {new_count} |
| ⚠️ Ухудшилось | {worsened} |
| ❌ Потеряно | {lost} |

**Вывод:** {comparison.summary}
"""
    
    comment += """
---

📄 Полный отчёт: `outputs/swot_latest.md`
"""
    
    return comment


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="SWOT Analyzer CLI")
    parser.add_argument("source_file", type=Path, help="Путь к .md файлу для анализа")
    parser.add_argument("--context", type=Path, default=Path("context.md"), help="Путь к context.md")
    parser.add_argument("--db", type=Path, default=Path("swot.db"), help="Путь к SQLite базе")
    parser.add_argument("--outputs", type=Path, default=Path("outputs"), help="Папка для результатов")
    parser.add_argument("--comment-file", type=Path, help="Файл для записи комментария к PR")
    
    args = parser.parse_args()
    
    if not args.source_file.exists():
        print(f"❌ Файл не найден: {args.source_file}")
        sys.exit(1)
    
    try:
        analysis, comparison, swot_path, comp_path = run_analysis(
            args.source_file,
            args.context,
            args.db,
            args.outputs
        )
        
        if args.comment_file:
            comment = generate_pr_comment(analysis, comparison)
            args.comment_file.write_text(comment, encoding='utf-8')
            print(f"💬 Комментарий: {args.comment_file}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
