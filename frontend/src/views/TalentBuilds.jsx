import { useEffect, useState } from 'react';
import { api } from '../api';

const LEVELS = [1, 4, 7, 10, 13, 16, 20];

export default function TalentBuilds() {
  const [heroes, setHeroes] = useState([]);
  const [hero, setHero] = useState('');
  const [gameType, setGameType] = useState('Storm League');
  const [builds, setBuilds] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.heroes().then((rows) => {
      setHeroes(rows);
      if (rows.length && !hero) setHero(rows[0].name);
    }).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!hero) return;
    api.heroTalents(hero, { game_type: gameType, limit: 5 }).then(setBuilds).catch((e) => setError(e.message));
  }, [hero, gameType]);

  return (
    <section>
      <h2>Talent Builds</h2>
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
      <div className="build-list">
        {builds.map((b, i) => (
          <div className="build-card" key={i}>
            <div className="build-card__head">
              <span>Win rate {b.win_rate?.toFixed(1) ?? '—'}%</span>
              <span>{b.games_played ?? '—'} games</span>
            </div>
            <ol className="build-card__talents">
              {LEVELS.map((lvl, idx) => (
                <li key={lvl}><b>{lvl}</b> {b.build[idx] || '—'}</li>
              ))}
            </ol>
          </div>
        ))}
        {!builds.length && <p className="empty">No talent builds cached yet for {hero}.</p>}
      </div>
    </section>
  );
}
