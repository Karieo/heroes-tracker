import { useEffect, useState } from 'react';
import { api } from '../api';

export default function HeroStats() {
  const [gameType, setGameType] = useState('Storm League');
  const [heroes, setHeroes] = useState([]);
  const [stats, setStats] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.heroes().then(setHeroes).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!heroes.length) return;
    Promise.all(heroes.map((h) => api.heroStats(h.name, { game_type: gameType })))
      .then((rows) => setStats(rows.filter((r) => r && r.hero)))
      .catch((e) => setError(e.message));
  }, [heroes, gameType]);

  const sorted = [...stats].sort((a, b) => (b.win_rate || 0) - (a.win_rate || 0));

  return (
    <section>
      <h2>Hero Stats</h2>
      <div className="filters">
        <select value={gameType} onChange={(e) => setGameType(e.target.value)}>
          <option value="Storm League">Storm League</option>
          <option value="Quick Match">Quick Match</option>
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      <table className="table">
        <thead>
          <tr>
            <th>Hero</th>
            <th>Win Rate</th>
            <th>Pick Rate</th>
            <th>Ban Rate</th>
            <th>Games</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => (
            <tr key={s.hero}>
              <td>{s.hero}</td>
              <td>{fmt(s.win_rate)}</td>
              <td>{fmt(s.pick_rate)}</td>
              <td>{fmt(s.ban_rate)}</td>
              <td>{s.games_played ?? '—'}</td>
            </tr>
          ))}
          {!sorted.length && (
            <tr><td colSpan={5} className="empty">No hero stats cached yet.</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

function fmt(v) {
  return v == null ? '—' : `${v.toFixed(1)}%`;
}
