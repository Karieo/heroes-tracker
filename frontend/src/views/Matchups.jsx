import { useEffect, useState } from 'react';
import { api } from '../api';

export default function Matchups() {
  const [heroes, setHeroes] = useState([]);
  const [hero, setHero] = useState('');
  const [gameType, setGameType] = useState('Storm League');
  const [rows, setRows] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.heroes().then((r) => {
      setHeroes(r);
      if (r.length && !hero) setHero(r[0].name);
    }).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!hero) return;
    api.heroMatchups(hero, { game_type: gameType }).then(setRows).catch((e) => setError(e.message));
  }, [hero, gameType]);

  return (
    <section>
      <h2>Matchup Lookup</h2>
      <div className="filters">
        <select value={hero} onChange={(e) => setHero(e.target.value)}>
          {heroes.map((h) => <option key={h.name} value={h.name}>{h.name}</option>)}
        </select>
        <select value={gameType} onChange={(e) => setGameType(e.target.value)}>
          <option value="Storm League">Storm League</option>
          <option value="Quick Match">Quick Match</option>
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      <table className="table">
        <thead>
          <tr>
            <th>Opponent</th>
            <th>{hero}'s win rate</th>
            <th>Games</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.opponent_hero}>
              <td>{r.opponent_hero}</td>
              <td>{r.win_rate?.toFixed(1) ?? '—'}%</td>
              <td>{r.games_played ?? '—'}</td>
            </tr>
          ))}
          {!rows.length && (
            <tr><td colSpan={3} className="empty">No matchup data cached yet for {hero}.</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
