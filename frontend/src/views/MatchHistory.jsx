import { useEffect, useState } from 'react';
import { api } from '../api';

export default function MatchHistory() {
  const [players, setPlayers] = useState([]);
  const [battletag, setBattletag] = useState('');
  const [gameType, setGameType] = useState('');
  const [matches, setMatches] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.listPlayers().then(setPlayers).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    const params = {};
    if (battletag) params.battletag = battletag;
    if (gameType) params.game_type = gameType;
    api.matches(params).then(setMatches).catch((e) => setError(e.message));
  }, [battletag, gameType]);

  return (
    <section>
      <h2>Match History</h2>
      <div className="filters">
        <select value={battletag} onChange={(e) => setBattletag(e.target.value)}>
          <option value="">Default player</option>
          {players.map((p) => (
            <option key={p.id} value={p.battletag}>{p.display_name}</option>
          ))}
        </select>
        <select value={gameType} onChange={(e) => setGameType(e.target.value)}>
          <option value="">All game types</option>
          <option value="Storm League">Storm League</option>
          <option value="Quick Match">Quick Match</option>
          <option value="ARAM">ARAM</option>
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      <table className="table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Map</th>
            <th>Hero</th>
            <th>Result</th>
            <th>Level</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((m) => (
            <tr key={m.match_id} className={m.won ? 'win' : 'loss'}>
              <td>{new Date(m.game_date).toLocaleString()}</td>
              <td>{m.game_type}</td>
              <td>{m.game_map}</td>
              <td>{m.hero}</td>
              <td>{m.won ? 'Win' : 'Loss'}</td>
              <td>{m.hero_level}</td>
            </tr>
          ))}
          {!matches.length && (
            <tr><td colSpan={6} className="empty">No matches synced yet — the backend polls HeroesProfile on a schedule.</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
