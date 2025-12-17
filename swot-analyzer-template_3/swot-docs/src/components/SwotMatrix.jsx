import React from 'react';

export default function SwotMatrix({ strengths, weaknesses, opportunities, threats }) {
  return (
    <div className="swot-matrix">
      <div className="swot-quadrant swot-strength">
        <h3>💪 Сильные стороны</h3>
        <ul>
          {strengths?.map((item, idx) => (
            <li key={idx} title={item.reasoning}>
              {item.text}
            </li>
          ))}
        </ul>
      </div>
      
      <div className="swot-quadrant swot-weakness">
        <h3>😰 Слабые стороны</h3>
        <ul>
          {weaknesses?.map((item, idx) => (
            <li key={idx} title={item.reasoning}>
              {item.text}
            </li>
          ))}
        </ul>
      </div>
      
      <div className="swot-quadrant swot-opportunity">
        <h3>🚀 Возможности</h3>
        <ul>
          {opportunities?.map((item, idx) => (
            <li key={idx} title={item.reasoning}>
              {item.text}
            </li>
          ))}
        </ul>
      </div>
      
      <div className="swot-quadrant swot-threat">
        <h3>⚠️ Угрозы</h3>
        <ul>
          {threats?.map((item, idx) => (
            <li key={idx} title={item.reasoning}>
              {item.text}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function SwotStats({ strengths, weaknesses, opportunities, threats }) {
  return (
    <div className="stats-grid">
      <div className="stat-card stat-s">
        <div className="stat-number">{strengths?.length || 0}</div>
        <div className="stat-label">Сильные</div>
      </div>
      <div className="stat-card stat-w">
        <div className="stat-number">{weaknesses?.length || 0}</div>
        <div className="stat-label">Слабые</div>
      </div>
      <div className="stat-card stat-o">
        <div className="stat-number">{opportunities?.length || 0}</div>
        <div className="stat-label">Возможности</div>
      </div>
      <div className="stat-card stat-t">
        <div className="stat-number">{threats?.length || 0}</div>
        <div className="stat-label">Угрозы</div>
      </div>
    </div>
  );
}
