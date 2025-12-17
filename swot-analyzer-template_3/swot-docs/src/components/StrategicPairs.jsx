import React from 'react';

function StrategyCard({ pair, type1, type2 }) {
  return (
    <div className="strategy-card">
      <div className="strategy-factors">
        <span className={`factor-tag factor-${type1.toLowerCase()}`}>
          {pair.factor1}
        </span>
        <span style={{ color: 'var(--ifm-color-emphasis-400)' }}>+</span>
        <span className={`factor-tag factor-${type2.toLowerCase()}`}>
          {pair.factor2}
        </span>
      </div>
      <div className="strategy-text">{pair.strategy}</div>
      {pair.risk && (
        <div className="risk-badge">
          ⚠️ Риск: {pair.risk}
        </div>
      )}
    </div>
  );
}

export default function StrategicPairs({ so, wo, st, wt }) {
  return (
    <>
      {so?.length > 0 && (
        <div className="strategic-section">
          <h3>🚀 S+O: Наступательная стратегия</h3>
          <p style={{ color: 'var(--ifm-color-emphasis-600)', marginBottom: '1rem' }}>
            Использовать сильные стороны для реализации возможностей
          </p>
          {so.map((pair, idx) => (
            <StrategyCard key={idx} pair={pair} type1="s" type2="o" />
          ))}
        </div>
      )}
      
      {wo?.length > 0 && (
        <div className="strategic-section">
          <h3>📈 W+O: Стратегия улучшений</h3>
          <p style={{ color: 'var(--ifm-color-emphasis-600)', marginBottom: '1rem' }}>
            Преодолеть слабости за счёт возможностей
          </p>
          {wo.map((pair, idx) => (
            <StrategyCard key={idx} pair={pair} type1="w" type2="o" />
          ))}
        </div>
      )}
      
      {st?.length > 0 && (
        <div className="strategic-section">
          <h3>🛡️ S+T: Защитная стратегия</h3>
          <p style={{ color: 'var(--ifm-color-emphasis-600)', marginBottom: '1rem' }}>
            Использовать силу для нейтрализации угроз
          </p>
          {st.map((pair, idx) => (
            <StrategyCard key={idx} pair={pair} type1="s" type2="t" />
          ))}
        </div>
      )}
      
      {wt?.length > 0 && (
        <div className="strategic-section">
          <h3>🔥 W+T: Минимизация рисков</h3>
          <p style={{ color: 'var(--ifm-color-emphasis-600)', marginBottom: '1rem' }}>
            Критические риски — слабости под угрозой
          </p>
          {wt.map((pair, idx) => (
            <StrategyCard key={idx} pair={pair} type1="w" type2="t" />
          ))}
        </div>
      )}
    </>
  );
}
