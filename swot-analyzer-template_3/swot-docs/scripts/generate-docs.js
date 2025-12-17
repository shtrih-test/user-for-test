#!/usr/bin/env node
/**
 * Генератор MDX файлов из SQLite базы SWOT-анализов
 * Запуск: node scripts/generate-docs.js --db ../swot.db
 */

const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');

// Парсинг аргументов
const args = process.argv.slice(2);
const dbPathArg = args.find(a => a.startsWith('--db='))?.split('=')[1] 
  || args[args.indexOf('--db') + 1] 
  || '../swot.db';

const dbPath = path.resolve(process.cwd(), dbPathArg);
const docsDir = path.resolve(__dirname, '../docs');

console.log(`📂 База данных: ${dbPath}`);
console.log(`📄 Папка docs: ${docsDir}`);

// Проверяем существование БД
if (!fs.existsSync(dbPath)) {
  console.error(`❌ База данных не найдена: ${dbPath}`);
  console.log('💡 Укажите путь: node generate-docs.js --db /path/to/swot.db');
  process.exit(1);
}

// Подключаемся к БД
const db = new Database(dbPath, { readonly: true });

// Создаём папки
const swotDir = path.join(docsDir, 'swot');
const compDir = path.join(docsDir, 'comparisons');
fs.mkdirSync(swotDir, { recursive: true });
fs.mkdirSync(compDir, { recursive: true });

// Функция очистки устаревших файлов
function cleanupOldFiles(dir, validIds, prefix = '') {
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.mdx') && !f.startsWith('_'));
  let removed = 0;
  
  files.forEach(file => {
    // Извлекаем ID из имени файла (формат: YYYY-MM-DD-ID.mdx)
    const match = file.match(/-(\d+)\.mdx$/);
    if (match) {
      const fileId = parseInt(match[1]);
      if (!validIds.includes(fileId)) {
        const filePath = path.join(dir, file);
        fs.unlinkSync(filePath);
        console.log(`   🗑️  Удалён устаревший: ${file}`);
        removed++;
      }
    }
  });
  
  return removed;
}

// Получаем все SWOT-анализы
const swotRows = db.prepare(`
  SELECT 
    sa.*,
    c.content as context_content
  FROM swot_analyses sa
  LEFT JOIN contexts c ON sa.context_id = c.id
  ORDER BY sa.created_at DESC
`).all();

console.log(`\n📊 Найдено SWOT-анализов: ${swotRows.length}`);

// Генерируем MDX для каждого SWOT
swotRows.forEach((row, index) => {
  const date = new Date(row.created_at);
  const dateStr = date.toISOString().split('T')[0];
  const timeStr = date.toTimeString().split(' ')[0].slice(0, 5);
  
  // Формируем slug
  const slug = `${dateStr}-${row.id}`;
  const isLatest = index === 0;
  
  // Парсим JSON
  const strengths = JSON.parse(row.strengths_json || '[]');
  const weaknesses = JSON.parse(row.weaknesses_json || '[]');
  const opportunities = JSON.parse(row.opportunities_json || '[]');
  const threats = JSON.parse(row.threats_json || '[]');
  const strategicSO = JSON.parse(row.strategic_so_json || '[]');
  const strategicWO = JSON.parse(row.strategic_wo_json || '[]');
  const strategicST = JSON.parse(row.strategic_st_json || '[]');
  const strategicWT = JSON.parse(row.strategic_wt_json || '[]');
  
  // Данные для компонентов (JSON inline)
  const swotData = {
    strengths,
    weaknesses,
    opportunities,
    threats,
  };
  
  const strategicData = {
    so: strategicSO,
    wo: strategicWO,
    st: strategicST,
    wt: strategicWT,
  };
  
  // Генерируем MDX
  const mdx = `---
sidebar_position: ${1000 - row.id}
title: "${isLatest ? '🆕 ' : ''}${dateStr} — ${row.source_file}"
description: "SWOT-анализ от ${dateStr} ${timeStr}"
---

import SwotMatrix, { SwotStats } from '@site/src/components/SwotMatrix';
import StrategicPairs from '@site/src/components/StrategicPairs';

# SWOT-анализ: ${row.source_file}

📅 **Дата:** ${dateStr} ${timeStr}  
📄 **Источник:** \`${row.source_file}\`  
🆔 **ID:** ${row.id}

---

## 📊 Обзор

<SwotStats 
  strengths={${JSON.stringify(strengths)}}
  weaknesses={${JSON.stringify(weaknesses)}}
  opportunities={${JSON.stringify(opportunities)}}
  threats={${JSON.stringify(threats)}}
/>

---

## 🎯 SWOT-матрица

<SwotMatrix 
  strengths={${JSON.stringify(strengths)}}
  weaknesses={${JSON.stringify(weaknesses)}}
  opportunities={${JSON.stringify(opportunities)}}
  threats={${JSON.stringify(threats)}}
/>

:::tip Подсказка
Наведите на пункт, чтобы увидеть обоснование
:::

---

## 🧭 Стратегическое сопоставление

<StrategicPairs 
  so={${JSON.stringify(strategicSO)}}
  wo={${JSON.stringify(strategicWO)}}
  st={${JSON.stringify(strategicST)}}
  wt={${JSON.stringify(strategicWT)}}
/>

---

## 📝 Детали

<details>
<summary>Сильные стороны (${strengths.length})</summary>

${strengths.map((s, i) => `
### ${i + 1}. ${s.text}

> ${s.reasoning}
`).join('\n')}

</details>

<details>
<summary>Слабые стороны (${weaknesses.length})</summary>

${weaknesses.map((w, i) => `
### ${i + 1}. ${w.text}

> ${w.reasoning}
`).join('\n')}

</details>

<details>
<summary>Возможности (${opportunities.length})</summary>

${opportunities.map((o, i) => `
### ${i + 1}. ${o.text}

> ${o.reasoning}
`).join('\n')}

</details>

<details>
<summary>Угрозы (${threats.length})</summary>

${threats.map((t, i) => `
### ${i + 1}. ${t.text}

> ${t.reasoning}
`).join('\n')}

</details>
`;

  // Записываем файл
  const filePath = path.join(swotDir, `${slug}.mdx`);
  fs.writeFileSync(filePath, mdx);
  console.log(`   ✅ ${slug}.mdx`);
});

// Очищаем устаревшие SWOT файлы
const validSwotIds = swotRows.map(r => r.id);
const removedSwot = cleanupOldFiles(swotDir, validSwotIds);
if (removedSwot > 0) {
  console.log(`   🧹 Удалено устаревших SWOT: ${removedSwot}`);
}

// Получаем сравнения
const compRows = db.prepare(`
  SELECT * FROM comparisons
  ORDER BY created_at DESC
`).all();

console.log(`\n🔄 Найдено сравнений: ${compRows.length}`);

// Генерируем MDX для сравнений
compRows.forEach((row, index) => {
  const date = new Date(row.created_at);
  const dateStr = date.toISOString().split('T')[0];
  const timeStr = date.toTimeString().split(' ')[0].slice(0, 5);
  
  const slug = `${dateStr}-${row.id}`;
  const isLatest = index === 0;
  
  const items = JSON.parse(row.items_json || '[]');
  
  const mdx = `---
sidebar_position: ${1000 - row.id}
title: "${isLatest ? '🆕 ' : ''}Сравнение ${dateStr}"
description: "Сравнение SWOT #${row.old_swot_id} → #${row.new_swot_id}"
---

import ComparisonTimeline, { ComparisonStats } from '@site/src/components/ComparisonTimeline';

# Сравнение SWOT-анализов

📅 **Дата:** ${dateStr} ${timeStr}  
🔄 **Версии:** #${row.old_swot_id} → #${row.new_swot_id}

---

<ComparisonTimeline 
  items={${JSON.stringify(items)}}
  summary={${JSON.stringify(row.summary || '')}}
/>
`;

  const filePath = path.join(compDir, `${slug}.mdx`);
  fs.writeFileSync(filePath, mdx);
  console.log(`   ✅ ${slug}.mdx`);
});

// Очищаем устаревшие файлы сравнений
const validCompIds = compRows.map(r => r.id);
const removedComp = cleanupOldFiles(compDir, validCompIds);
if (removedComp > 0) {
  console.log(`   🧹 Удалено устаревших сравнений: ${removedComp}`);
}

// Закрываем БД
db.close();

console.log('\n✅ Генерация завершена!');
console.log(`\n📌 Запустите сервер: npm start`);
