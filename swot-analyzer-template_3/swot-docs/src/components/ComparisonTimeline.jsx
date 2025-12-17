import React from 'react';

const typeLabels = {
  improved: '✅ Улучшено',
  new: '🆕 Новое',
  worsened: '⚠️ Ухудшилось',
  lost: '❌ Потеряно',
};

const categoryLabels = {
  S: 'Сильная сторона',
  W: 'Слабая сторона',
  O: 'Возможность',
  T: 'Угроза',
};

function ChangeItem({ item }) {
  return (
    <div className={`change-item change-${item.change_type}`}>
      <div className="change-header">
        <span className={`change-type type-${item.change_type}`}>
          {typeLabels[item.change_type] || item.change_type}
        </span>
        <span className="change-category">
          {categoryLabels[item.category] || item.category}
        </span>
      </div>
      
      <div className="change-content">
        {item.old_text && (
          <div className="change-old">{item.old_text}</div>
        )}
        {item.old_text && item.new_text && (
          <div className="change-arrow">→</div>
        )}
        {item.new_text && (
          <div className="change-new-text">{item.new_text}</div>
        )}
        {!item.old_text && !item.new_text && (
          <div style={{ gridColumn: '1 / -1', color: 'var(--ifm-color-emphasis-500)' }}>
            Нет данных
          </div>
        )}
      </div>
      
      {item.reasoning && (
        <div className="change-reasoning">
          💡 {item.reasoning}
        </div>
      )}
    </div>
  );
}

export default function ComparisonTimeline({ items, summary }) {
  // Группируем по типу изменения
  const grouped = {
    improved: items?.filter(i => i.change_type === 'improved') || [],
    new: items?.filter(i => i.change_type === 'new') || [],
    worsened: items?.filter(i => i.change_type === 'worsened') || [],
    lost: items?.filter(i => i.change_type === 'lost') || [],
  };
  
  return (
    <>
      {summary && (
        <div className="summary-card">
          <h3>📋 Главный вывод</h3>
          <p>{summary}</p>
        </div>
      )}
      
      <ComparisonStats items={items} />
      
      <div className="comparison-timeline">
        {grouped.improved.map((item, idx) => (
          <ChangeItem key={`imp-${idx}`} item={item} />
        ))}
        {grouped.new.map((item, idx) => (
          <ChangeItem key={`new-${idx}`} item={item} />
        ))}
        {grouped.worsened.map((item, idx) => (
          <ChangeItem key={`wor-${idx}`} item={item} />
        ))}
        {grouped.lost.map((item, idx) => (
          <ChangeItem key={`lost-${idx}`} item={item} />
        ))}
      </div>
    </>
  );
}

export function ComparisonStats({ items }) {
  if (!items) return null;
  
  const stats = {
    improved: items.filter(i => i.change_type === 'improved').length,
    new: items.filter(i => i.change_type === 'new').length,
    worsened: items.filter(i => i.change_type === 'worsened').length,
    lost: items.filter(i => i.change_type === 'lost').length,
  };
  
  return (
    <div className="stats-grid">
      <div className="stat-card stat-s">
        <div className="stat-number">{stats.improved}</div>
        <div className="stat-label">Улучшено</div>
      </div>
      <div className="stat-card stat-o">
        <div className="stat-number">{stats.new}</div>
        <div className="stat-label">Новое</div>
      </div>
      <div className="stat-card stat-t">
        <div className="stat-number">{stats.worsened}</div>
        <div className="stat-label">Ухудшилось</div>
      </div>
      <div className="stat-card stat-w">
        <div className="stat-number">{stats.lost}</div>
        <div className="stat-label">Потеряно</div>
      </div>
    </div>
  );
}
